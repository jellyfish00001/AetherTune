"""可重跑 Desktop streaming 核心／PortAudio／CABLE 證據；輸入為注入 WAV。"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    import numpy as np
    import sounddevice as sd
    import soundfile as sf
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", choices=["seed-vc", "meanvc2", "xvc"], required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=15)
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--postfx", action="store_true")
    parser.add_argument("--noise-reduction", action="store_true")
    parser.add_argument("--model", choices=["40ms", "120ms"], default="40ms")
    parser.add_argument("--parameters", type=Path, help="引擎參數 JSON；由正式 runner 校驗範圍與交叉限制")
    parser.add_argument("--source", type=Path, default=ROOT / "dataset/reference-voices/voice-male-m1.wav")
    args = parser.parse_args()
    parameters = {"model": args.model} if args.engine == "meanvc2" else {}
    if args.parameters:
        supplied = json.loads(args.parameters.read_text(encoding="utf-8"))
        if not isinstance(supplied, dict):
            raise ValueError("參數 JSON 必須是 object")
        parameters.update(supplied)
    folder = args.output_dir.resolve()
    folder.mkdir(parents=True, exist_ok=False)
    request = dict(reference=str(ROOT / "dataset/reference-voices/voice-female-f1.wav"),
                   input="麥克風 (HyperX QuadCast S)", output="CABLE Input (VB-Audio Virtual Cable)",
                   host_api="Windows DirectSound", parameters=parameters, monitor=dict(enabled=False),
                   noise_reduction=dict(enabled=args.noise_reduction, strength_db=12),
                   postfx=dict(enabled=args.postfx, wet=.5, low_db=3, high_db=-2, reverb_mix=.15))
    request_path = folder / "request.json"
    request_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
    apis = sd.query_hostapis()
    candidates = [i for i, d in enumerate(sd.query_devices()) if d["name"] == "CABLE Output (VB-Audio Virtual Cable)"
                  and apis[d["hostapi"]]["name"] == "Windows WASAPI" and d["max_input_channels"] >= 2]
    if len(candidates) != 1:
        raise ValueError("loopback endpoint 必須唯一")
    command = [str(ROOT / f"tools/venvs/{args.engine}/Scripts/python.exe"), "-u", "-B",
               str(ROOT / "services/engines/stream_runtime.py"), "--root", str(ROOT), "--engine", args.engine,
               "--request", str(request_path), "--output-dir", str(folder), "--test-source",
               str(args.source.resolve()), "--test-seconds", str(args.seconds)]
    import os
    started = time.perf_counter()
    process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    running = threading.Event()
    events = []
    captured = []
    capture_status = []
    def observe():
        with (folder / "runtime.log").open("w", encoding="utf-8") as log:
            for line in process.stdout:
                log.write(line)
                log.flush()
                try:
                    event = json.loads(line)
                    if event.get("type") == "vc_runtime":
                        print(json.dumps(event, ensure_ascii=False), flush=True)
                        events.append(event)
                        if event.get("value") == "RUNNING":
                            running.set()
                except (ValueError, AttributeError):
                    pass
    reader = threading.Thread(target=observe, daemon=True)
    reader.start()
    def capture(indata, _frames, _times, status):
        captured.append(indata.copy())
        if status:
            capture_status.append(str(status))
    stream = None
    try:
        deadline = started + args.timeout
        while not running.wait(.2):
            if process.poll() is not None or time.perf_counter() >= deadline:
                break
        if running.is_set():
            stream = sd.InputStream(device=candidates[0], samplerate=48000, channels=2,
                                    dtype="float32", blocksize=960, callback=capture)
            stream.start()
        while process.poll() is None and time.perf_counter() < deadline:
            time.sleep(.2)
        if process.poll() is None:
            process.stdin.write("stop\n")
            process.stdin.flush()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        process.wait()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        if stream:
            stream.abort()
            stream.close()
        process.stdin.close()
        reader.join(timeout=2)
    report = dict(engine=args.engine, exit_code=process.returncode, seconds=time.perf_counter()-started,
                  input_kind="injected_wav", physical_mic_verified=False, audio_verified=False,
                  events=events, capture_status=capture_status)
    if captured:
        data = np.concatenate(captured)
        wav = folder / "cable-loopback.wav"
        sf.write(wav, data, 48000)
        report.update(loopback=str(wav), loopback_sha256=hashlib.sha256(wav.read_bytes()).hexdigest(),
                      loopback_peak=float(np.max(np.abs(data))), loopback_rms=float(np.sqrt(np.mean(data.astype(np.float64)**2))),
                      loopback_finite=bool(np.isfinite(data).all()))
    evidence_path = folder / "stream-evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8")) if evidence_path.is_file() else {}
    report["runtime_evidence"] = evidence
    passed = (process.returncode == 0 and evidence.get("nonzero") and evidence.get("finite")
              and report.get("loopback_finite") and report.get("loopback_rms", 0) > 1e-5)
    report["status"] = "PASS" if passed else "BLOCKED"
    (folder / "smoke-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report.get(key) for key in ("engine", "status", "exit_code", "seconds", "loopback_rms")}), flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
