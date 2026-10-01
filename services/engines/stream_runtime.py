"""Desktop VC 共用音訊生命週期。模型在 worker 執行，PortAudio callback 只搬 PCM。"""
from __future__ import annotations

import argparse
from collections import deque
from contextlib import ExitStack
import hashlib
import json
import signal
import sys
import threading
import time
from pathlib import Path


def emit(event: dict) -> None:
    print(json.dumps(event, ensure_ascii=False), flush=True)


def state(value: str, reason: str) -> None:
    emit(dict(type="vc_runtime", value=value, reason=reason, audio_verified=False))


class SampleFifo:
    """以 frame 限制 backlog；超量捨棄最舊樣本，避免延遲無限累積。"""
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.chunks = deque()
        self.frames = 0
        self.dropped = 0
        self.lock = threading.Lock()

    def push(self, samples):
        import numpy as np
        samples = np.asarray(samples, dtype=np.float32).copy()
        with self.lock:
            self.chunks.append(samples)
            self.frames += len(samples)
            excess = max(0, self.frames - self.capacity)
            self.dropped += excess
            while excess:
                first = self.chunks.popleft()
                count = min(excess, len(first))
                if count < len(first):
                    self.chunks.appendleft(first[count:])
                self.frames -= count
                excess -= count

    def pop(self, count: int, *, partial=False):
        import numpy as np
        with self.lock:
            if not partial and self.frames < count:
                return None
            available = min(count, self.frames)
            remaining = available
            pieces = []
            while remaining:
                first = self.chunks.popleft()
                take = min(remaining, len(first))
                pieces.append(first[:take])
                if take < len(first):
                    self.chunks.appendleft(first[take:])
                self.frames -= take
                remaining -= take
            return np.concatenate(pieces) if pieces else np.empty(0, dtype=np.float32)


def run(root: Path, engine: str, request: dict, folder: Path, *, test_source=None, test_seconds=15) -> int:
    import numpy as np
    import sounddevice as sd
    import soundfile as sf
    from scipy.signal import resample_poly
    from services.engines.postfx import PostFx
    from services.engines.rvc_runtime import endpoint, digest
    from services.engines.streaming_adapters import create_processor

    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    folder.mkdir(parents=True, exist_ok=True)
    report = dict(engine=engine, status="LOADING", route=request, audio_verified=False,
                  input_kind="injected_wav" if test_source else "physical_device",
                  scope="Desktop callback/worker/output; physical listening and 600s LIVE are separate")
    path = folder / "stream-evidence.json"
    def save():
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    save()
    worker = None
    errors = []
    capture = []
    capture_frames = 0
    try:
        state("LOADING", f"載入 {engine} 常駐模型與參考聲音")
        load_started = time.perf_counter()
        processor = create_processor(root, engine, request["parameters"], request["reference"], folder)
        fx = PostFx(48000, request.get("postfx"))
        report.update(runtime=processor.runtime, reference_sha256=digest(Path(request["reference"])), postfx=fx.settings)
        emit(dict(type="runtime", runtime=processor.runtime))
        state("LOADING", "模型已載入，預熱推論核心")
        # 與真實 worker 相同的核心；warmup 結束重置模型 context，無 synthetic PASS。
        probe = (.03 * np.sin(np.arange(processor.block) * (2*np.pi*220/48000))).astype(np.float32)
        for _ in range(3):
            processor.process(probe)
        processor.reset()
        report["load_seconds"] = time.perf_counter() - load_started
        # 避免 Faiss／Torch DLL 載入與阻塞 CRT stdin reader 同時進行。
        def control():
            for line in sys.stdin:
                if line.strip() == "stop":
                    stop.set()
                    return
            stop.set()
        threading.Thread(target=control, daemon=True, name="vc-control").start()
        if stop.is_set():
            report["status"] = "CANCELLED"
            return 0
        state("READY", "模型與預熱完成，正在開啟麥克風和輸出裝置")
        input_index = endpoint(sd, request["input"], request["host_api"], "input", 1)
        output_index = endpoint(sd, request["output"], request["host_api"], "output", 2)
        incoming = SampleFifo(max(processor.block * 3, 48000))
        outgoing = SampleFifo(24000)
        monitoring = SampleFifo(24000)
        pending = threading.Event()
        stats = dict(blocks=0, input_frames=0, output_frames=0, input_peak=0.0, output_peak=0.0,
                     underruns=0, overruns=0, empty_output_callbacks=0, monitor_frames=0, monitor_peak=0.0)
        peaks = dict(input_peak=0.0, output_peak=0.0)
        timings = deque(maxlen=4096)
        callback_hash = hashlib.sha256()
        source_audio = None
        source_position = 0
        if test_source:
            source_audio, source_rate = sf.read(test_source, dtype="float32", always_2d=True)
            source_audio = source_audio.mean(axis=1)
            if source_rate != 48000:
                import math
                divisor = math.gcd(source_rate, 48000)
                source_audio = resample_poly(source_audio, 48000//divisor, source_rate//divisor).astype(np.float32)
            if not len(source_audio) or not np.isfinite(source_audio).all() or not np.any(source_audio):
                raise ValueError("SOURCE_INVALID: injection 必須是有限非零 WAV")
            report["source_sha256"] = digest(Path(test_source))
        monitor = request.get("monitor") or dict(enabled=False)
        distinct_monitor = monitor.get("enabled") and (monitor["output"], monitor["host_api"]) != (request["output"], request["host_api"])
        report["monitor_status"] = "active" if distinct_monitor else "same_output" if monitor.get("enabled") else "off"
        stream_started = 0.0
        first_input = None
        first_output = None

        def fail(exc):
            errors.append(str(exc))
            stop.set()
            pending.set()

        def input_callback(indata, _frames, _times, status):
            nonlocal source_position, first_input
            if stop.is_set():
                raise sd.CallbackStop
            try:
                mono = indata.mean(axis=1)
                if source_audio is not None:
                    indices = (np.arange(len(mono)) + source_position) % len(source_audio)
                    mono = source_audio[indices]
                    source_position += len(mono)
                if not np.isfinite(mono).all():
                    raise ValueError("AUDIO_INVALID: 麥克風輸入非有限")
                peak = float(np.max(np.abs(mono)))
                stats["input_peak"] = max(stats["input_peak"], peak)
                peaks["input_peak"] = max(peaks["input_peak"], peak)
                stats["input_frames"] += len(mono)
                stats["overruns"] += int(bool(status.input_overflow))
                if first_input is None and peak > 1e-4:
                    first_input = time.perf_counter()
                incoming.push(mono)
                pending.set()
            except Exception as exc:
                fail(exc)
                raise sd.CallbackAbort from exc

        def output_callback(outdata, frames, _times, status):
            nonlocal first_output, capture_frames
            outdata.fill(0)
            if stop.is_set():
                raise sd.CallbackStop
            try:
                samples = outgoing.pop(frames, partial=True)
                outdata[:len(samples)] = samples[:, None]
                peak = float(np.max(np.abs(outdata)))
                stats["output_peak"] = max(stats["output_peak"], peak)
                peaks["output_peak"] = max(peaks["output_peak"], peak)
                stats["output_frames"] += len(samples)
                stats["underruns"] += int(bool(status.output_underflow))
                stats["empty_output_callbacks"] += int(len(samples) < frames)
                if first_output is None and peak > 1e-4:
                    first_output = time.perf_counter()
                callback_hash.update(outdata.tobytes())
                if source_audio is not None and capture_frames < 48000 * (test_seconds + 2):
                    capture.append(outdata[:, 0].copy())
                    capture_frames += frames
            except Exception as exc:
                fail(exc)
                raise sd.CallbackAbort from exc

        def monitor_callback(outdata, frames, _times, _status):
            outdata.fill(0)
            if stop.is_set():
                raise sd.CallbackStop
            try:
                samples = monitoring.pop(frames, partial=True)
                outdata[:len(samples)] = samples[:, None]
                stats["monitor_frames"] += len(samples)
                stats["monitor_peak"] = max(stats["monitor_peak"], float(np.max(np.abs(outdata))))
            except Exception as exc:
                fail(exc)
                raise sd.CallbackAbort from exc

        def convert():
            try:
                while not stop.is_set():
                    block = incoming.pop(processor.block)
                    if block is None:
                        pending.wait(.05)
                        pending.clear()
                        continue
                    started = time.perf_counter()
                    result = processor.process(block)
                    timings.append((time.perf_counter()-started)*1000)
                    stats["blocks"] += 1
                    if result is not None and len(result):
                        result = fx.process(result)
                        outgoing.push(result)
                        if distinct_monitor:
                            monitoring.push(result)
            except Exception as exc:
                fail(exc)

        with ExitStack() as streams:
            output_stream = streams.enter_context(sd.OutputStream(device=output_index, samplerate=48000,
                channels=2, dtype="float32", blocksize=960, callback=output_callback))
            monitor_stream = None
            if distinct_monitor:
                monitor_index = endpoint(sd, monitor["output"], monitor["host_api"], "output", 2)
                monitor_stream = streams.enter_context(sd.OutputStream(device=monitor_index, samplerate=48000,
                    channels=2, dtype="float32", blocksize=960, callback=monitor_callback))
            input_stream = streams.enter_context(sd.InputStream(device=input_index, samplerate=48000,
                channels=1, dtype="float32", blocksize=960, callback=input_callback))
            worker = threading.Thread(target=convert, daemon=True, name="vc-inference")
            worker.start()
            stream_started = time.perf_counter()
            report["status"] = "RUNNING"
            state("RUNNING", "麥克風 → 變聲 → 音效 → 輸出已啟動")
            while not stop.wait(.5):
                elapsed = time.perf_counter() - stream_started
                if not input_stream.active or not output_stream.active or (monitor_stream is not None and not monitor_stream.active):
                    raise ValueError("STREAM_FAILED: 音訊裝置停止回呼")
                timing = dict(p95_ms=float(np.percentile(list(timings), 95)) if timings else None,
                              rtf=float(np.mean(timings)) / (processor.block/48) if timings else None)
                metrics = {**stats, **timing, "input_drops": incoming.dropped, "output_drops": outgoing.dropped,
                           "monitor_drops": monitoring.dropped, "input_backlog_ms": incoming.frames/48}
                report.update(metrics=metrics, elapsed_seconds=elapsed)
                emit(dict(type="metrics", metrics={**metrics, **peaks}))
                peaks.update(input_peak=0.0, output_peak=0.0)
                if first_input is None and elapsed > 5:
                    state("RUNNING", "串流已開啟，但未收到有效輸入；請檢查麥克風靜音與所選裝置")
                elif first_output is None and first_input is not None and time.perf_counter()-first_input > 5:
                    state("RUNNING", "已收到輸入，但尚無非零變聲輸出；請查看處理速度與 backend log")
                elif timing["rtf"] is not None and timing["rtf"] > 1:
                    state("RUNNING", "模型處理慢於輸入，可能斷續；請查看 RTF 與丟棄樣本數")
                save()
                if source_audio is not None and elapsed >= test_seconds:
                    stop.set()
            if errors:
                raise ValueError("CALLBACK_FAILED: " + errors[0])
        report.update(status="STOPPED", metrics={**report.get("metrics", {}), **stats}, nonzero=stats["output_peak"] > 1e-4, finite=True,
                      callback_sha256=callback_hash.hexdigest(), first_output_seconds=(first_output-stream_started) if first_output else None,
                      first_input_seconds=(first_input-stream_started) if first_input else None)
        if capture:
            wav = folder / "callback-output.wav"
            rendered = np.concatenate(capture)
            sf.write(wav, rendered, 48000)
            report.update(output=str(wav), output_sha256=digest(wav), rms=float(np.sqrt(np.mean(rendered.astype(np.float64)**2))))
        state("OFFLINE", "串流已停止並釋放裝置；請核對當輪音訊證據")
        return 0
    except Exception as exc:
        report.update(status="BLOCKED", error=str(exc))
        state("ERROR", str(exc))
        raise
    finally:
        stop.set()
        if worker:
            worker.join(timeout=2)
        save()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--engine", choices=["seed-vc", "meanvc2", "xvc"], required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--test-source", type=Path)
    parser.add_argument("--test-seconds", type=float, default=15)
    args = parser.parse_args()
    sys.path.insert(0, str(args.root.resolve()))
    from services.engines.runner_service import validate
    request = json.loads(args.request.read_text(encoding="utf-8"))
    _, values = validate(args.root, args.engine, request)
    request["parameters"] = values
    return run(args.root.resolve(), args.engine, request, args.output_dir.resolve(), test_source=args.test_source, test_seconds=args.test_seconds)


if __name__ == '__main__':
    raise SystemExit(main())
