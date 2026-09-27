"""Record a user-selected mic and two downstream loopback points for Seed-VC timing evidence.

Run this only after the official Seed-VC GUI is configured and waiting on its Start button.
The recorder reads devices explicitly and never changes the Windows default endpoints.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import queue
import sys
import threading
import time
import uuid
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import sounddevice as sd
import soundfile as sf


ROOT = Path(__file__).resolve().parent.parent
TELEMETRY_PATH = Path(__file__).with_name("portaudio-callback-telemetry.py")
SPEC = importlib.util.spec_from_file_location("portaudio_callback_telemetry", TELEMETRY_PATH)
assert SPEC and SPEC.loader
TELEMETRY_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TELEMETRY_MODULE)
WAV_SPEC = importlib.util.spec_from_file_location("wav_evidence", Path(__file__).with_name("wav-evidence.py"))
assert WAV_SPEC and WAV_SPEC.loader
WAV_MODULE = importlib.util.module_from_spec(WAV_SPEC)
WAV_SPEC.loader.exec_module(WAV_MODULE)


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _device_inventory() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    hostapis = [dict(item) for item in sd.query_hostapis()]
    devices = [dict(item) for item in sd.query_devices()]
    for device in devices:
        host_index = device.get("hostapi")
        device["hostapi_name"] = (
            hostapis[int(host_index)]["name"]
            if isinstance(host_index, int) and 0 <= host_index < len(hostapis)
            else ""
        )
    return hostapis, devices


def _resolve_input_device(
    devices: list[dict[str, Any]], host_api: str, exact_name: str, label: str, sample_rate: int
) -> tuple[dict[str, Any], int]:
    matches = [
        item for item in devices
        if item.get("hostapi_name") == host_api
        and str(item.get("name", "")) == exact_name
        and int(item.get("max_input_channels", 0)) > 0
    ]
    if len(matches) != 1:
        raise ValueError(
            f"{label} must identify exactly one recording endpoint in Host API {host_api!r}; "
            f"found {len(matches)} for {exact_name!r}. Run --list-devices and select exact names."
        )
    device = matches[0]
    channels = min(2, int(device["max_input_channels"]))
    sd.check_input_settings(
        device=int(device["index"]), channels=channels, samplerate=sample_rate, dtype="float32"
    )
    return device, channels


class Recorder:
    """Bounded callback queue lets disk writes happen off PortAudio's real-time thread."""

    def __init__(self, label: str, device: dict[str, Any], channels: int, rate: int, path: Path) -> None:
        self.label = label
        self.device = device
        self.channels = channels
        self.rate = rate
        self.path = path
        self.buffers: queue.Queue[np.ndarray | None] = queue.Queue(maxsize=64)
        self.telemetry = TELEMETRY_MODULE.CallbackTelemetry(rate)
        self.first_onset_portaudio_sec: float | None = None
        self.first_onset_perf_counter: float | None = None
        self.callback_errors: list[str] = []
        self.dropped_frames = 0
        self.recorded_frames = 0
        self._writer_error: str | None = None
        self._writer = threading.Thread(target=self._write_worker, name=f"wav-writer-{label}", daemon=True)
        self._writer.start()
        self._started = False
        self._closed = False
        try:
            self.stream = sd.InputStream(
                device=int(device["index"]),
                samplerate=rate,
                channels=channels,
                blocksize=max(1, rate // 100),
                dtype="float32",
                callback=self._callback,
            )
        except Exception:
            self._finish_writer()
            raise

    def _write_worker(self) -> None:
        try:
            with sf.SoundFile(str(self.path), mode="w", samplerate=self.rate, channels=self.channels, subtype="PCM_16") as wav:
                while True:
                    block = self.buffers.get()
                    if block is None:
                        break
                    wav.write(block)
                    self.recorded_frames += int(len(block))
        except Exception as exc:  # surfaced in the final evidence report
            self._writer_error = f"{type(exc).__name__}: {exc}"

    def _callback(self, indata: np.ndarray, frames: int, times: Any, status: Any) -> None:
        try:
            self.telemetry.record(int(frames), times, status)
            now = time.perf_counter()
            if self.first_onset_portaudio_sec is None and len(indata):
                peaks = np.max(np.abs(indata), axis=1)
                active = np.flatnonzero(peaks >= _ACTIVE_THRESHOLD)
                if active.size:
                    adc_time = getattr(times, "inputBufferAdcTime", None)
                    if isinstance(adc_time, (int, float)):
                        self.first_onset_portaudio_sec = float(adc_time) + float(active[0]) / self.rate
                    self.first_onset_perf_counter = now - max(0, frames - int(active[0])) / self.rate
        except Exception as exc:
            self.callback_errors.append(f"{type(exc).__name__}: {exc}")
        try:
            self.buffers.put_nowait(np.array(indata, dtype=np.float32, copy=True))
        except queue.Full:
            self.dropped_frames += int(frames)
        except Exception as exc:
            self.callback_errors.append(f"audio queue: {type(exc).__name__}: {exc}")

    def start(self) -> None:
        self.stream.start()
        self._started = True

    def stop(self) -> None:
        if self._closed:
            return
        stream_error: Exception | None = None
        try:
            if self._started:
                self.stream.stop()
        except Exception as exc:
            stream_error = exc
        finally:
            try:
                self.stream.close()
            finally:
                self._finish_writer()
                self._closed = True
        if stream_error is not None:
            self.callback_errors.append(f"stream stop: {type(stream_error).__name__}: {stream_error}")

    def _finish_writer(self) -> None:
        # 若 writer 已崩潰，避免在已滿的 queue 上無限等待；否則以 timeout 等它取出 sentinel。
        while self._writer.is_alive():
            try:
                self.buffers.put(None, timeout=0.25)
                break
            except queue.Full:
                continue
        self._writer.join(timeout=30)
        if self._writer.is_alive():
            self._writer_error = self._writer_error or "writer did not stop within 30 seconds"

    def report(self) -> dict[str, Any]:
        result = {
            "device": {
                "index": int(self.device["index"]),
                "name": self.device["name"],
                "host_api": self.device["hostapi_name"],
                "sample_rate_hz": self.rate,
                "channels": self.channels,
            },
            "callback": self.telemetry.snapshot(),
            "recorded_frames": self.recorded_frames,
            "dropped_frames": self.dropped_frames,
            "first_active_sample_portaudio_seconds": self.first_onset_portaudio_sec,
            "first_active_sample_perf_counter_seconds": self.first_onset_perf_counter,
            "writer_error": self._writer_error,
            "callback_errors": self.callback_errors,
        }
        if not self._writer.is_alive() and self.path.is_file() and self.path.stat().st_size > 44:
            result["wav"] = {"path": str(self.path), "sha256": _hash(self.path), "bytes": self.path.stat().st_size}
            with wave.open(str(self.path), "rb") as wav:
                result["wav"].update(
                    sample_rate_hz=wav.getframerate(), channels=wav.getnchannels(), frames=wav.getnframes(),
                    duration_seconds=wav.getnframes() / wav.getframerate(),
                )
        else:
            result["wav"] = None
        return result


_ACTIVE_THRESHOLD = 10.0 ** (-40.0 / 20.0)


def _write_report(path: Path, report: dict[str, Any]) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list-devices", action="store_true", help="唯讀列舉輸入端點，不開 stream")
    parser.add_argument("--host-api", default="Windows WASAPI")
    parser.add_argument("--microphone")
    parser.add_argument("--backend-loopback", help="通常是 CABLE Output 的錄音端點名稱")
    parser.add_argument("--terminal-loopback", help="通常是 Voicemeeter Out B1 的錄音端點名稱")
    parser.add_argument("--reference-audio", type=Path, help="LIVE evidence 對應的已授權 PCM WAV reference")
    parser.add_argument("--sample-rate", type=int, default=48000)
    parser.add_argument("--seconds", type=int, default=30, help="先做短測；穩定後才指定 600")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "artifacts" / "seed-vc" / "real-capture")
    args = parser.parse_args()

    run_id: str | None = None
    run_dir: Path | None = None
    reference_report: dict[str, Any] | None = None
    try:
        hostapis, devices = _device_inventory()
        if args.list_devices:
            print("PortAudio recording endpoints (read-only, no streams):")
            for item in devices:
                if int(item.get("max_input_channels", 0)) > 0:
                    print(
                        f"#{item['index']} [{item['hostapi_name']}] {item['name']} "
                        f"(max input channels={item['max_input_channels']})"
                    )
            print("Host APIs: " + ", ".join(str(item.get("name")) for item in hostapis))
            return 0 if devices else 3

        if not args.microphone or not args.backend_loopback or not args.terminal_loopback:
            raise ValueError("請提供 --microphone、--backend-loopback、--terminal-loopback；先用 --list-devices 檢查名稱。")
        if args.reference_audio is None:
            raise ValueError("請提供 --reference-audio，使用同一個 Seed-VC GUI session 實際選用的 reference PCM WAV。")
        if args.sample_rate <= 0 or args.seconds < 1:
            raise ValueError("sample rate 和 seconds 必須為正整數。")
        reference_path = args.reference_audio.expanduser().resolve()
        reference_report = WAV_MODULE.validate_wav(reference_path)
        if reference_report["non_zero"] is not True:
            raise ValueError(f"reference WAV 是靜音檔：{reference_path}")
        selected = [args.microphone, args.backend_loopback, args.terminal_loopback]
        if len(set(selected)) != 3:
            raise ValueError("實體麥克風、backend loopback、終端 loopback 必須是三個不同的 endpoint。")

        chosen: list[tuple[dict[str, Any], int]] = []
        for label, name in zip(("microphone", "backend_loopback", "terminal_loopback"), selected):
            chosen.append(_resolve_input_device(devices, args.host_api, name, label, args.sample_rate))

        run_id = uuid.uuid4().hex
        run_dir = (args.output_dir.expanduser().resolve() / run_id)
        run_dir.mkdir(parents=True, exist_ok=False)
        names = ("microphone.wav", "backend-loopback.wav", "terminal-loopback.wav")
        recorders: list[Recorder] = []
        try:
            for (label, (device, channels), name) in zip(
                ("microphone", "backend_loopback", "terminal_loopback"), chosen, names
            ):
                recorders.append(Recorder(label, device, channels, args.sample_rate, run_dir / name))
        except Exception:
            for recorder in reversed(recorders):
                try:
                    recorder.stop()
                except Exception:
                    pass
            raise
        start_utc = datetime.now(timezone.utc).isoformat()
        start_perf = time.perf_counter()
        capture_error: str | None = None
        try:
            for recorder in recorders:
                recorder.start()
            print(
                f"CAPTURE RUN {run_id}: {args.seconds}s. 請在已啟動的 Seed-VC GUI 按 Start，"
                "並在錄製期間對麥克風說話；此 runner 不會操作 GUI 或改 Windows 預設裝置。",
                flush=True,
            )
            time.sleep(args.seconds)
        except KeyboardInterrupt:
            capture_error = "KeyboardInterrupt: capture was interrupted by the user"
        except Exception as exc:
            capture_error = f"{type(exc).__name__}: {exc}"
        finally:
            stop_errors: list[str] = []
            for recorder in reversed(recorders):
                try:
                    recorder.stop()
                except Exception as exc:
                    stop_errors.append(f"{recorder.label}: {type(exc).__name__}: {exc}")
        end_perf = time.perf_counter()
        end_utc = datetime.now(timezone.utc).isoformat()
        outputs = {recorder.label: recorder.report() for recorder in recorders}
        onsets = {
            label: outputs[label]["first_active_sample_portaudio_seconds"]
            for label in outputs
        }
        mic_onset = onsets["microphone"]
        timing = {
            "clock": "PortAudio inputBufferAdcTime; same explicitly selected host API",
            "capture_to_backend_first_active_sample_ms": (
                (onsets["backend_loopback"] - mic_onset) * 1000
                if mic_onset is not None and onsets["backend_loopback"] is not None
                else None
            ),
            "capture_to_terminal_first_active_sample_ms": (
                (onsets["terminal_loopback"] - mic_onset) * 1000
                if mic_onset is not None and onsets["terminal_loopback"] is not None
                else None
            ),
            "e2e_first_packet_ms": (
                (onsets["terminal_loopback"] - mic_onset) * 1000
                if mic_onset is not None and onsets["terminal_loopback"] is not None
                else None
            ),
            "measurement_note": "音訊 onset threshold estimate; cross-device clock alignment and output content must be manually reviewed before LIVE classification.",
        }
        callback_flags_clear = all(
            not outputs[label]["callback"]["input_overflows"]
            and not outputs[label]["callback"]["input_underflows"]
            and not outputs[label]["callback"]["output_underflows"]
            and not outputs[label]["callback"]["output_overflows"]
            and not outputs[label]["callback"]["invalid_frame_counts"]
            and not outputs[label]["callback"]["status_messages"]
            and outputs[label]["dropped_frames"] == 0
            for label in outputs
        )
        continuity_ready = all(
            outputs[label]["callback"]["frame_continuity_status"] == "PASS"
            for label in outputs
        )
        all_wavs = all(
            outputs[label]["wav"]
            and outputs[label]["recorded_frames"] > 0
            and outputs[label]["wav"]["frames"] == outputs[label]["recorded_frames"]
            and outputs[label]["wav"]["duration_seconds"] >= args.seconds * 0.95
            and outputs[label]["callback"]["continuous_seconds_from_frames"] >= args.seconds * 0.95
            and outputs[label]["writer_error"] is None
            and not outputs[label]["callback_errors"]
            and outputs[label]["callback"]["callback_count"] > 0
            for label in outputs
        )
        report = {
            "schema_version": "aethertune-seed-vc-real-capture/v1",
            "run_id": run_id,
            "status": (
                "BLOCKED" if capture_error or stop_errors
                else "PASS" if all_wavs and callback_flags_clear and continuity_ready
                else "WAITING"
            ),
            "live_gate_status": "WAITING",
            "capture_error": capture_error,
            "started_at_utc": start_utc,
            "completed_at_utc": end_utc,
            "requested_seconds": args.seconds,
            "observed_seconds": end_perf - start_perf,
            "host_api": args.host_api,
            "input_threshold_dbfs": -40.0,
            "reference_audio": reference_report,
            "output_points": outputs,
            "timing_ms": timing,
            "portaudio_flags_clear": callback_flags_clear,
            "frame_continuity_ready": continuity_ready,
            "stream_stop_errors": stop_errors,
            "manual_review": {
                "human_listening_completed": False,
                "review_record": None,
                "required_before_live_candidate": True,
            },
            "limitations": [
                "Onset timing is a threshold estimate and requires a spoken test phrase; it is not automatically a LIVE decision.",
                "The official GUI callback status is not exposed by upstream; this recorder measures its own microphone/loopback capture streams.",
                "A run under 600 seconds is a short screening only; 600 seconds plus zero flags and manual listening are required for live_candidate stability review.",
            ],
        }
        report_path = run_dir / "seed-vc-real-capture.json"
        _write_report(report_path, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"Capture report: {report_path}")
        return {"PASS": 0, "WAITING": 3, "BLOCKED": 2}[report["status"]]
    except Exception as exc:
        if run_id is not None and run_dir is not None and run_dir.is_dir():
            report_path = run_dir / "seed-vc-real-capture.json"
            if not report_path.exists():
                try:
                    _write_report(
                        report_path,
                        {
                            "schema_version": "aethertune-seed-vc-real-capture/v1",
                            "run_id": run_id,
                            "status": "BLOCKED",
                            "live_gate_status": "WAITING",
                            "requested_seconds": args.seconds,
                            "host_api": args.host_api,
                            "reference_audio": reference_report,
                            "capture_error": f"{type(exc).__name__}: {exc}",
                            "manual_review": {"human_listening_completed": False, "review_record": None},
                        },
                    )
                    print(f"Capture failure report: {report_path}")
                except Exception as report_exc:
                    print(f"BLOCKED: could not write failure report: {type(report_exc).__name__}: {report_exc}")
        print(f"BLOCKED: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
