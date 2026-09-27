"""正式 SpeechManager → TTS → 指定 CABLE route 的唯本機音訊驗證。"""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
import numpy as np
import sounddevice as sd
import soundfile as sf


def digest(path: Path) -> str:
    # 長時間 loopback 不整檔讀入 RAM。
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", default="cosyvoice", choices=["cosyvoice", "breeze"])
    parser.add_argument("--voice", required=True)
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--text-file", type=Path)
    cancel = parser.add_mutually_exclusive_group()
    cancel.add_argument("--cancel-after", type=int)
    cancel.add_argument("--cancel-on-playing", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    folder = args.output.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    text = (args.text_file or root / "app/tests/fixtures/manual-text.txt").resolve()
    devices, apis = sd.query_devices(), sd.query_hostapis()
    # 只錄 CABLE Output，不讀實體麥克風或最終混音，也不改全域預設裝置。
    matches = [i for i, device in enumerate(devices)
               if device["name"] == "CABLE Output (VB-Audio Virtual Cable)"
               and apis[device["hostapi"]]["name"] == "Windows DirectSound"
               and device["max_input_channels"] >= 2]
    if len(matches) != 1:
        raise RuntimeError(f"CABLE capture endpoint 不唯一：{matches}")
    capture = folder / "cable-loopback.wav"
    frames = 0
    peak = 0.0
    squares = 0.0
    finite = True
    audio_errors: list[str] = []
    blocks: list[tuple[float, int, float, float]] = []
    lock = threading.Lock()
    with sf.SoundFile(capture, mode="w", samplerate=48000, channels=2, subtype="PCM_16") as output:
        def callback(data, count, timing, status):
            nonlocal frames, peak, squares, finite
            with lock:
                if status:
                    audio_errors.append(str(status))
                finite = finite and bool(np.isfinite(data).all())
                peak = max(peak, float(np.max(np.abs(data))))
                squares += float(np.sum(data.astype(np.float64) ** 2))
                frames += count
                blocks.append((time.time(), count, float(np.max(np.abs(data))), float(np.sum(data.astype(np.float64) ** 2))))
                output.write(data)
        argv = [str(root / "app/src-tauri/target/debug/speech-probe.exe"), args.engine, args.voice, str(text), str(args.count)]
        if args.cancel_after is not None:
            argv.append(str(args.cancel_after))
        elif args.cancel_on_playing:
            argv.append("playing")
        with sd.InputStream(device=matches[0], samplerate=48000, channels=2, dtype="float32", blocksize=960, callback=callback):
            with (folder / "probe.jsonl").open("w", encoding="utf-8") as log:
                # 正式 probe 自己擁有 Windows Job；失敗或退出由同一 manager 清理。
                process = subprocess.Popen(argv, cwd=root, stdout=log, stderr=subprocess.STDOUT)
                try:
                    code = process.wait(timeout=720 * args.count + 45)
                    time.sleep(0.3)
                except subprocess.TimeoutExpired:
                    code = -1
                    audio_errors.append("formal probe timed out after the per-request bounded budget")
                finally:
                    if process.poll() is None:
                        process.terminate()
                        process.wait(timeout=10)
    events = []
    for line in (folder / "probe.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    snapshots = [event["snapshot"] for event in events if event.get("type") == "probe_snapshot"]
    segments = []
    cancelled_segments = []
    # 對照每句真正 playback callback 的時間，確認 20 次測試不是只有一次非零擷取。
    for request in (snapshots[-1]["queue"] if snapshots else []):
        if request["status"] != "completed":
            continue
        metrics = request["metrics"]
        start = datetime.fromisoformat(metrics["first_playback_audio_at"].replace("Z", "+00:00")).timestamp()
        end = datetime.fromisoformat(metrics["playback_completed_at"].replace("Z", "+00:00")).timestamp()
        window = [block for block in blocks if start - 0.05 <= block[0] <= end + 0.3]
        segment_frames = sum(block[1] for block in window)
        segment_peak = max((block[2] for block in window), default=0.0)
        segments.append({"request_id": request["id"], "frames": segment_frames, "peak": segment_peak,
                         "rms": (sum(block[3] for block in window) / max(segment_frames * 2, 1)) ** 0.5,
                         "status": "PASS" if segment_peak > 0.0001 else "BLOCKED"})
    if args.cancel_on_playing:
        for event in (event for event in events if event.get("type") == "probe_cancel" and event.get("mode") == "playing"):
            request = next(request for request in snapshots[-1]["queue"] if request["id"] == event["request_id"])
            start = datetime.fromisoformat(request["metrics"]["playback_started_at"].replace("Z", "+00:00")).timestamp()
            end = event["at_unix_ms"] / 1000
            window = [block for block in blocks if start <= block[0] <= end + 0.3]
            segment_peak = max((block[2] for block in window), default=0.0)
            cancelled_segments.append({"request_id":request["id"], "frames":sum(block[1] for block in window),
                                       "peak":segment_peak, "status":"PASS" if request["status"]=="cancelled" and segment_peak>0.0001 else "BLOCKED"})
    report = {
        "status": "PASS" if code == 0 and finite and (peak > 0.0001 or args.cancel_after is not None) and not audio_errors and all(segment["status"] == "PASS" for segment in segments + cancelled_segments) and (not args.cancel_on_playing or len(cancelled_segments)==1) else "BLOCKED",
        "scope": "real generation/playback/CABLE capture; external Post-FX and physical Mic E2E WAITING",
        "command": argv, "exit_code": code, "probe_pid": process.pid,
        "capture_device": dict(devices[matches[0]]), "host_api": "Windows DirectSound",
        "sample_rate": 48000, "channels": 2, "frames": frames, "finite": finite,
        "peak": peak, "rms": (squares / max(frames * 2, 1)) ** 0.5,
        "capture_status": audio_errors, "capture": str(capture),
        "capture_sha256": digest(capture),
        "text_sha256": digest(text),
        "request_count": args.count, "cancel_test": args.cancel_after is not None or args.cancel_on_playing,
        "cancel_on_playing": args.cancel_on_playing,
        "completed_playback_segments": segments,
        "cancelled_playback_segments": cancelled_segments,
    }
    (folder / "audio-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
