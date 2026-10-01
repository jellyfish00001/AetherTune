"""Desktop RVC block runner：登錄模型、CUDA FCPE/RMVPE、明確音訊端點。

block/SOLA 邏輯改寫自固定 RVC upstream realtime_gui.py（MIT）：
https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI
revision 81eed5e8f68b6bed1789f682fe78cdd324495afc
Copyright (c) 2023 liujing04, 源文雨, Ftps

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import queue
import signal
import sys
import threading
import time
from collections import deque
from pathlib import Path

REVISION = "81eed5e8f68b6bed1789f682fe78cdd324495afc"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def registered_model(root: Path, model_id: str) -> dict:
    with (root / "models/model-register.csv").open(encoding="utf-8-sig", newline="") as stream:
        matches = [row for row in csv.DictReader(stream) if row["model_id"] == model_id]
    if len(matches) != 1:
        raise ValueError("MODEL_NOT_FOUND: RVC model_id 必須唯一且已登錄")
    row = matches[0]
    for field, suffix in (("weights", ".pth"), ("index", ".index")):
        path = (root / row[f"{field}_relative_path"]).resolve()
        if not path.is_relative_to(root.resolve()) or path.suffix != suffix or not path.is_file():
            raise ValueError(f"MODEL_NOT_FOUND: 登錄的 {field} 路徑無效")
        if digest(path).lower() != row[f"{field}_sha256"].lower():
            raise ValueError(f"MODEL_HASH_MISMATCH: {model_id} {field}")
        row[field] = str(path)
    return row


def endpoint(sd, name: str, api: str, direction: str, channels: int) -> int:
    apis = sd.query_hostapis()
    matches = [i for i, device in enumerate(sd.query_devices())
               if device["name"] == name and apis[device["hostapi"]]["name"] == api
               and device[f"max_{direction}_channels"] >= channels]
    if len(matches) != 1:
        raise ValueError(f"DEVICE_NOT_FOUND: {direction} name + host_api 必須唯一：{name} / {api}")
    return matches[0]


class RvcProcessor:
    """重用 upstream 推論核心；保留 rolling context 和 SOLA，不啟動官方 GUI。"""

    sample_rate = 48000

    def __init__(self, root: Path, model: dict, values: dict):
        import faulthandler
        # 載入逾時保留堆疊並退出，bridge 會回報 BACKEND_CRASH，不無限等待。
        faulthandler.dump_traceback_later(120, exit=True)
        event("LOADING", "核對 RVC source revision")
        repo = root / "tools/external/Retrieval-based-Voice-Conversion-WebUI"
        # 只讀固定 checkout 的 Git metadata，避免 native Job 內再啟動 Git console
        # 與 control stdin 共用 handle；此查核不寫 repo，也不載入浮動 revision。
        git_dir = repo / ".git"
        if git_dir.is_file():
            git_dir = (repo / git_dir.read_text(encoding="utf-8").strip().removeprefix("gitdir: ")).resolve()
        actual = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
        if actual.startswith("ref: "):
            ref = actual[5:]
            target = (git_dir / ref).resolve()
            if not target.is_relative_to(git_dir.resolve()):
                raise ValueError("SOURCE_REVISION_MISMATCH: Git ref 路徑無效")
            if target.is_file():
                actual = target.read_text(encoding="utf-8").strip()
            else:
                entries = (git_dir / "packed-refs").read_text(encoding="utf-8").splitlines()
                actual = next((line.split()[0] for line in entries if line.endswith(" " + ref)), "")
        if actual != REVISION:
            raise ValueError(f"SOURCE_REVISION_MISMATCH: RVC {actual}")
        os.chdir(repo)
        os.environ["RVC_CUDA_GRAPH"] = "0"
        os.environ["HF_HUB_OFFLINE"] = "1"
        sys.path.insert(0, str(repo))
        argv = sys.argv
        sys.argv = [argv[0], "--noautoopen"]
        try:
            event("LOADING", "載入 Torch 與 RVC imports")
            # 先載入 Faiss，保持 DLL 初始化順序固定。
            import faiss
            import torch
            import numpy as np
            from torchaudio.transforms import Resample
            from configs.config import Config
            from infer.rtrvc import RVC
            event("LOADING", "初始化 RVC CUDA config")
            config = Config()
        finally:
            sys.argv = argv
        if not torch.cuda.is_available() or str(config.device).split(":")[0] != "cuda":
            raise ValueError("CUDA_UNAVAILABLE: RVC Desktop 要求 CUDA，不暗中回退 CPU")
        self.torch, self.np = torch, np
        self.device = config.device
        self.values = values
        event("LOADING", "載入 HuBERT、角色模型與 index")
        self.rvc = RVC(values["pitch"], 0.0, model["weights"], model["index"], values["index_rate"], config)
        if self.rvc.net_g is None or not hasattr(self.rvc, "tgt_sr"):
            raise ValueError("MODEL_LOAD_FAILED: RVC upstream 未完成模型初始化")
        self.block = int(values["chunk"] * 48)
        self.crossfade = int(values["crossfade"] * 48)
        self.overlap = min(self.crossfade, 1920)
        self.search = 480
        self.extra = int(round(values["extra_time"] * 100)) * 480
        count = self.extra + self.crossfade + self.search + self.block
        self.input = torch.zeros(count, device=self.device)
        self.input16 = torch.zeros(count // 3, device=self.device)
        self.previous = torch.zeros(self.overlap, device=self.device)
        self.fade = torch.sin(0.5 * np.pi * torch.linspace(0, 1, self.overlap, device=self.device)) ** 2
        self.kernel = torch.ones(1, 1, self.overlap, device=self.device)
        self.resample_in = Resample(48000, 16000).to(self.device)
        self.resample_out = Resample(self.rvc.tgt_sr, 48000).to(self.device) if self.rvc.tgt_sr != 48000 else None
        self.runtime = {"device": str(self.device), "gpu": torch.cuda.get_device_name(0), "torch": torch.__version__,
                        "source_revision": actual, "f0_method": values["f0_method"],
                        "source_hashes": {name: digest(repo / name) for name in ("infer/rtrvc.py", "infer/fcpe.py", "infer/hubert.py")}}
        # 先初始化 FCPE／kernel；第一個真實 callback 不支付這筆載入成本。
        probe = np.sin(np.arange(self.block) * (2 * np.pi * 220 / 48000)).astype("float32") * 0.03
        for _ in range(3):
            self.process(probe)
        f0_model = self.rvc.model_fcpe.infer_model.model if values["f0_method"] == "fcpe" else self.rvc.model_rmvpe.model
        f0_device = str(next(f0_model.parameters()).device)
        if not f0_device.startswith("cuda"):
            raise ValueError("CUDA_UNAVAILABLE: F0 model 未在 CUDA 執行")
        f0_path = root / ".venv/Lib/site-packages/torchfcpe/assets/fcpe_c_v001.pt" if values["f0_method"] == "fcpe" else repo / "assets/rmvpe/rmvpe.pt"
        self.runtime.update(f0_device=f0_device, f0_sha256=digest(f0_path), hubert_sha256=digest(repo / "assets/hubert_base/pytorch_model.bin"))
        faulthandler.cancel_dump_traceback_later()
        self.input.zero_()
        self.input16.zero_()
        self.previous.zero_()
        self.rvc.cache_pitch.zero_()
        self.rvc.cache_pitchf.zero_()

    def process(self, mono):
        torch, np = self.torch, self.np
        if len(mono) != self.block or not np.isfinite(mono).all():
            raise ValueError("AUDIO_INVALID: RVC block 長度或樣本無效")
        with torch.inference_mode():
            self.input[:-self.block] = self.input[self.block:].clone()
            self.input[-self.block:] = torch.from_numpy(mono).to(self.device)
            block16 = self.block // 3
            self.input16[:-block16] = self.input16[block16:].clone()
            self.input16[-block16 - 160:] = self.resample_in(self.input[-self.block - 960:])[160:]
            audio = self.rvc.infer(self.input16, block16, self.extra // 480,
                                   (self.block + self.overlap + self.search) // 480, self.values["f0_method"])
            if self.resample_out is not None:
                audio = self.resample_out(audio)
            conv = audio[None, None, :self.overlap + self.search]
            numerator = torch.nn.functional.conv1d(conv, self.previous[None, None, :])
            denominator = torch.sqrt(torch.nn.functional.conv1d(conv ** 2, self.kernel) + 1e-8)
            offset = int(torch.argmax(numerator / denominator).item())
            audio = audio[offset:]
            audio[:self.overlap] *= self.fade
            audio[:self.overlap] += self.previous * (1 - self.fade)
            self.previous[:] = audio[self.block:self.block + self.overlap]
            result = audio[:self.block].cpu().numpy().astype("float32", copy=True)
        if len(result) != self.block or not np.isfinite(result).all():
            raise ValueError("AUDIO_INVALID: RVC 輸出非有限或 frame 不足")
        return result


def event(value: str, reason: str) -> None:
    print(json.dumps({"type": "rvc_runtime", "value": value, "reason": reason, "audio_verified": False}, ensure_ascii=False), flush=True)


def run(root: Path, request: dict, values: dict, folder: Path) -> int:
    import numpy as np
    import sounddevice as sd
    import soundfile as sf
    from scipy.signal import resample_poly
    root, folder = root.resolve(), folder.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    model = registered_model(root, values["model_id"])
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())

    def control():
        for line in sys.stdin:
            if line.strip() == 'stop':
                stop.set()
                break
        stop.set()

    report = {"status": "LOADING", "source_mode": values["source_mode"], "model_id": model["model_id"],
              "model_sha256": model["weights_sha256"], "index_sha256": model["index_sha256"],
              "model_metadata_status": model["status"], "parameters": values, "route": request,
              "audio_verified": False, "scope": "RVC block/callback evidence; physical mic, listening and LIVE are separate"}
    report_path = folder / "rvc-evidence.json"

    def save():
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    save()
    try:
        load_started = time.perf_counter()
        processor = RvcProcessor(root, model, values)
        report.update(runtime=processor.runtime, load_seconds=time.perf_counter() - load_started)
        sys.path.insert(0, str(root))
        from services.engines.postfx import PostFx
        fx = PostFx(48000, request.get("postfx"))
        report["postfx"] = fx.settings
        print(json.dumps({"type": "runtime", "runtime": processor.runtime}, ensure_ascii=False), flush=True)
        # Windows CRT 的阻塞 stdin reader 會卡住 Faiss DLL 初始化；warmup 完成後
        # 才啟用控制執行緒。載入中的 Stop 仍由 service timeout／Job cleanup 保證。
        threading.Thread(target=control, name="rvc-control", daemon=True).start()
        event("READY", "RVC 模型與 F0 warmup 完成；音訊待驗證")
        if stop.is_set():
            report["status"] = "CANCELLED"
            return 0
        output_index = endpoint(sd, request["output"], request["host_api"], "output", 2)
        monitor = request.get("monitor") or {"enabled": False}
        report["status"] = "RUNNING"
        if values["source_mode"] == "file":
            source = Path(request["source"]).resolve()
            audio, rate = sf.read(source, dtype="float32", always_2d=True)
            mono = audio.mean(axis=1)
            if rate != 48000:
                import math
                divisor = math.gcd(rate, 48000)
                mono = resample_poly(mono, 48000 // divisor, rate // divisor).astype("float32")
            if not np.isfinite(mono).all() or not np.any(mono):
                raise ValueError("SOURCE_INVALID: 來源 WAV 為全零或非有限")
            converted = []
            timings = []
            event("RUNNING", "RVC 使用同一個 rolling block 核心轉換來源 WAV")
            # 加尾端 silence 排出 overlap；輸出 frame 數維持與來源一致。
            padded = np.pad(mono, (0, processor.block + (-len(mono) % processor.block)))
            for start in range(0, len(padded), processor.block):
                if stop.is_set():
                    report["status"] = "CANCELLED"
                    return 0
                started = time.perf_counter()
                converted.append(fx.process(processor.process(padded[start:start + processor.block])))
                timings.append((time.perf_counter() - started) * 1000)
            rendered = np.concatenate(converted)[:len(mono)]
            if not np.any(rendered):
                raise ValueError("AUDIO_INVALID: RVC 輸出全零")
            wav = folder / "output.wav"
            sf.write(wav, rendered, 48000)
            sys.path.insert(0, str(root))
            from services.tts.playback import MonitoredPlayback, PlaybackCancelled
            playback = MonitoredPlayback()
            try:
                result = playback.play(wav, {"output": request["output"], "host_api": request["host_api"], "monitor": monitor}, stop)
            except PlaybackCancelled:
                report["status"] = "CANCELLED"
                return 0
            report.update(status="PASS", source_sha256=digest(source), output_sha256=digest(wav), output=str(wav),
                          finite=True, nonzero=True, rms=float(np.sqrt(np.mean(rendered.astype("float64") ** 2))),
                          playback=vars(result), block_count=len(timings), p50_ms=float(np.percentile(timings, 50)), p95_ms=float(np.percentile(timings, 95)))
        else:
            input_index = endpoint(sd, request["input"], request["host_api"], "input", 1)
            stats = {"blocks": 0, "input_peak": 0.0, "output_peak": 0.0, "underruns": 0, "overruns": 0, "monitor_drops": 0}
            callback_digest = hashlib.sha256()
            timings = deque(maxlen=4096)
            errors = []
            monitor_stream = None
            pending = queue.Queue(maxsize=8)
            report["monitor_status"] = "same_output" if monitor.get("enabled") and monitor["output"] == request["output"] else "off"

            def callback(indata, outdata, frames, _times, status):
                outdata.fill(0)
                try:
                    if stop.is_set():
                        raise sd.CallbackStop
                    started = time.perf_counter()
                    converted = fx.process(processor.process(indata.mean(axis=1)))
                    outdata[:] = converted[:, None]
                    callback_digest.update(outdata.tobytes())
                    stats["blocks"] += 1
                    stats["input_peak"] = max(stats["input_peak"], float(np.max(np.abs(indata))))
                    stats["output_peak"] = max(stats["output_peak"], float(np.max(np.abs(converted))))
                    stats["underruns"] += int(bool(status.output_underflow))
                    stats["overruns"] += int(bool(status.input_overflow))
                    timings.append((time.perf_counter() - started) * 1000)
                    if monitor_stream is not None:
                        try:
                            pending.put_nowait(converted.copy())
                        except queue.Full:
                            stats["monitor_drops"] += 1
                except (sd.CallbackStop, sd.CallbackAbort):
                    raise
                except Exception as exc:
                    errors.append(str(exc))
                    stop.set()
                    raise sd.CallbackAbort from exc

            def monitor_callback(outdata, _frames, _times, _status):
                outdata.fill(0)
                try:
                    outdata[:] = pending.get_nowait()[:, None]
                    stats["monitor_frames"] = stats.get("monitor_frames", 0) + len(outdata)
                    stats["monitor_peak"] = max(stats.get("monitor_peak", 0.0), float(np.max(np.abs(outdata))))
                    stats["monitor_underruns"] = stats.get("monitor_underruns", 0) + int(bool(_status.output_underflow))
                except queue.Empty:
                    pass
                except Exception as exc:
                    report.update(monitor_status="failed", monitor_error=str(exc))
                    raise sd.CallbackAbort from exc

            if monitor.get("enabled") and monitor["output"] != request["output"]:
                try:
                    monitor_index = endpoint(sd, monitor["output"], monitor["host_api"], "output", 2)
                    monitor_stream = sd.OutputStream(device=monitor_index, samplerate=48000, channels=2,
                        dtype="float32", blocksize=processor.block, callback=monitor_callback)
                    monitor_stream.start()
                    report["monitor_status"] = "active"
                except Exception as exc:
                    report.update(monitor_status="failed", monitor_error=str(exc))
                    if monitor_stream is not None:
                        try:
                            monitor_stream.close()
                        except Exception:
                            pass
                        monitor_stream = None
            try:
                with sd.Stream(device=(input_index, output_index), samplerate=48000, channels=(1, 2),
                               dtype="float32", blocksize=processor.block, callback=callback):
                    event("RUNNING", "RVC duplex stream 已啟動；輸入與主輸出使用明確裝置")
                    while not stop.wait(0.5):
                        metrics = {**stats, "p95_ms": float(np.percentile(list(timings), 95)) if timings else None,
                                   "rtf": float(np.mean(timings)) / (processor.block / 48) if timings else None,
                                   "input_drops": 0, "output_drops": 0}
                        report.update(metrics=metrics)
                        print(json.dumps({"type": "metrics", "metrics": metrics}), flush=True)
                        save()
                if errors:
                    raise ValueError("CALLBACK_FAILED: " + errors[0])
            finally:
                if monitor_stream is not None:
                    try:
                        monitor_stream.abort()
                        monitor_stream.close()
                        if report.get("monitor_status") != "failed":
                            report["monitor_status"] = "stopped"
                    except Exception as exc:
                        report.update(monitor_status="failed", monitor_error=str(exc))
            report.update(status="STOPPED", metrics=stats, finite=True, nonzero=stats["output_peak"] > 0,
                          callback_sha256=callback_digest.hexdigest(), output_frames=stats["blocks"] * processor.block,
                          p50_ms=float(np.percentile(list(timings), 50)) if timings else None,
                          p95_ms=float(np.percentile(list(timings), 95)) if timings else None)
        event("OFFLINE", "RVC run 完成；請核對 evidence，LIVE 仍需另驗收")
        return 0
    except Exception as exc:
        report.update(status="BLOCKED", error=str(exc))
        event("ERROR", str(exc))
        raise
    finally:
        save()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    request = json.loads(args.request.read_text(encoding="utf-8"))
    sys.path.insert(0, str(args.root.resolve()))
    from services.engines.runner_service import validate
    _, values = validate(args.root.resolve(), "rvc", request)
    return run(args.root, request, values, args.output_dir)


if __name__ == "__main__":
    raise SystemExit(main())
