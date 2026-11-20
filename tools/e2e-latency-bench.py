"""Play/rec pulse train and estimate mic-to-output E2E latency (optional sounddevice/numpy).

loopback 模式：輸出裝置直接回授到輸入（例如 CABLE Input → CABLE Output），量測 OS／驅動 baseline。
engine 模式需兩條獨立路由（不可在同一裝置上 play/rec）：bench 播至 CABLE Input → 引擎擷取 CABLE Output →
引擎輸出至 Voicemeeter Input → bench 錄 Voicemeeter Out B1（對齊 seed-vc-virtual-route）。
baseline 為未掛引擎時相同兩跳迴授，或兩段單跳 loopback 之和。此為注入虛擬線量測，不含實體麥 ADC／耳機 DAC，
不是實體麥克風 E2E，不能作為 LIVE gate 的麥克風來源證據。
變聲引擎可能無法忠實複製 click；建議 `--signal chirp`，低 confidence 脈衝會標為 missing。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
ANALYSIS_PATH = Path(__file__).with_name("e2e_latency_analysis.py")


def _load_analysis():
    spec = importlib.util.spec_from_file_location("e2e_latency_analysis", ANALYSIS_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return out.stdout.strip() or None
    except Exception:
        return None


def _resolve_device(query, needle: str, kind: str, hostapi_index: int | None = None) -> tuple[int, str]:
    devices = [dict(item) for item in query()]
    for position, item in enumerate(devices):
        item.setdefault("index", position)
    if hostapi_index is not None:
        # 同一裝置在 MME／DirectSound／WASAPI／WDM-KS 各出現一次；只在指定 host API 內比對。
        devices = [item for item in devices if int(item.get("hostapi", -1)) == hostapi_index]
    needle_l = needle.strip().lower()
    if needle_l.isdigit():
        idx = int(needle_l)
        for item in devices:
            if int(item["index"]) == idx:
                return idx, str(item.get("name", ""))
        raise ValueError(f"device index out of range: {idx}")
    matches = []
    for item in devices:
        name = str(item.get("name", ""))
        if needle_l in name.lower():
            ch_in = int(item.get("max_input_channels", 0))
            ch_out = int(item.get("max_output_channels", 0))
            if kind == "input" and ch_in > 0:
                matches.append(item)
            elif kind == "output" and ch_out > 0:
                matches.append(item)
    exact = [item for item in matches if str(item.get("name", "")).strip().lower() == needle_l]
    if len(matches) > 1 and len(exact) == 1:
        matches = exact
    if len(matches) != 1:
        raise ValueError(f"{kind} device {needle!r}: expected 1 match, found {len(matches)}")
    dev = matches[0]
    return int(dev["index"]), str(dev.get("name", ""))


def _validate_timing(args, pulse_len: int) -> None:
    pulse_ms = pulse_len * 1000.0 / args.sample_rate
    if args.interval_ms <= args.max_delay_ms + pulse_ms:
        print(
            f"interval_ms ({args.interval_ms}) must exceed max_delay_ms + pulse length "
            f"({args.max_delay_ms} + {pulse_ms:.3f} = {args.max_delay_ms + pulse_ms:.3f}) to avoid pulse aliasing",
            file=sys.stderr,
        )
        raise SystemExit(2)


def _format_one_line_summary(report: dict[str, Any]) -> str:
    s = report.get("summary") or {}
    verdict = report.get("target_verdict") or "WAITING"

    def _ms(key: str) -> str:
        v = s.get(key)
        if v is None:
            return "n/a"
        return f"{float(v):.2f}ms"

    return (
        f"min={_ms('min_ms')} p50={_ms('p50_ms')} p95={_ms('p95_ms')} "
        f"max={_ms('max_ms')} verdict={verdict}"
    )


def _print_one_line_summary(report: dict[str, Any]) -> None:
    print(_format_one_line_summary(report))


def _run_self_test(args, analysis) -> int:
    import random

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    ref, onsets, template, pulse_len = analysis.build_pulse_train(
        args.signal,
        args.sample_rate,
        pulse_count=args.pulses,
        interval_ms=args.interval_ms,
    )
    _validate_timing(args, pulse_len)
    delay_samples = args.self_test_delay_ms * args.sample_rate / 1000.0
    recorded = analysis.apply_fractional_delay(ref, delay_samples)
    rng = random.Random(42)
    recorded = analysis.inject_noise(recorded, 22.0, rng)
    recorded = [x * 0.9 for x in recorded]
    analysis.write_wav_pcm16(out_dir / "reference.wav", ref, args.sample_rate)
    analysis.write_wav_float32(out_dir / "recorded.wav", recorded, args.sample_rate)
    meta = {
        "sample_rate": args.sample_rate,
        "pulse_onsets": onsets,
        "pulse_len": pulse_len,
        "template": template,
    }
    (out_dir / "pulses.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    per_pulse = analysis.estimate_delays(
        ref,
        recorded,
        args.sample_rate,
        onsets,
        pulse_len,
        template=template,
        max_delay_ms=args.max_delay_ms,
    )
    summary = analysis.summarize(per_pulse)
    extra: dict[str, Any] = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "self_test": True,
        "self_test_delay_ms": args.self_test_delay_ms,
    }
    report = analysis.build_report(
        "loopback_baseline",
        sample_rate=args.sample_rate,
        per_pulse=per_pulse,
        summary=summary,
        input_device="synthetic",
        output_device="synthetic",
        host_api="",
        extra=extra,
    )
    (out_dir / "e2e-latency-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _print_one_line_summary(report)
    return 0 if report["target_verdict"] in ("PASS", "WAITING") else 1


def _dry_run(args, analysis) -> int:
    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    ref, onsets, template, pulse_len = analysis.build_pulse_train(
        args.signal,
        args.sample_rate,
        pulse_count=args.pulses,
        interval_ms=args.interval_ms,
    )
    _validate_timing(args, pulse_len)
    plan = {
        "mode": "loopback_baseline" if args.mode == "loopback" else "through_engine",
        "sample_rate": args.sample_rate,
        "pulses": args.pulses,
        "interval_ms": args.interval_ms,
        "signal": args.signal,
        "blocksize": args.blocksize,
        "input_device": args.input_device if args.input_device else None,
        "output_device": args.output_device if args.output_device else None,
        "host_api": args.host_api,
        "pulse_onsets": onsets,
        "pulse_len": pulse_len,
        "dry_run": True,
    }
    (out_dir / "e2e-latency-plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    analysis.write_wav_pcm16(out_dir / "reference.wav", ref, args.sample_rate)
    meta = {
        "sample_rate": args.sample_rate,
        "pulse_onsets": onsets,
        "pulse_len": pulse_len,
        "template": template,
    }
    (out_dir / "pulses.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"dry-run OK: {out_dir}")
    return 0


def _build_speech_train(args):
    """speech 訊號：取參考語音能量最高的一段，以固定間隔重複。

    以內容為主的引擎（MeanVC2、RVC）會把 chirp／click 這類非語音脈衝轉成近乎靜音，
    脈衝互相關量不到；語音片段經轉換後音節包絡時間仍保留，可用包絡互相關估延遲。
    """
    import numpy as np
    import soundfile as sf

    sr = args.sample_rate
    audio, rate = sf.read(str(args.speech_wav), dtype="float32", always_2d=True)
    mono = audio.mean(axis=1)
    if rate != sr:
        positions = np.arange(int(len(mono) * sr / rate)) * (rate / sr)
        mono = np.interp(positions, np.arange(len(mono)), mono).astype(np.float32)
    n = int(round(sr * args.speech_ms / 1000.0))
    hop = sr // 100
    energy = np.convolve(mono.astype(np.float64) ** 2, np.ones(n), "valid")[::hop]
    start = int(np.argmax(energy)) * hop
    snippet = mono[start:start + n].astype(np.float32).copy()
    snippet *= 0.5 / max(1e-6, float(np.abs(snippet).max()))
    fade = sr // 200
    ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
    snippet[:fade] *= ramp
    snippet[-fade:] *= ramp[::-1]
    interval = int(round(sr * args.interval_ms / 1000.0))
    first = int(round(sr * 0.05))
    onsets = [first + k * interval for k in range(args.pulses)]
    total = onsets[-1] + n + int(round(sr * 0.2))
    ref = np.zeros(total, dtype=np.float32)
    for onset in onsets:
        ref[onset:onset + n] = snippet
    return ref.tolist(), onsets, snippet.tolist(), n


def _estimate_speech_delays(recorded, onsets, template, sr: int, max_delay_ms: float, threshold: float = 0.5):
    """對數 RMS 包絡（10 ms 窗、5 ms hop）正規化互相關；解析度 5 ms。"""
    import numpy as np

    hop = sr // 200
    win = sr // 100

    def envelope(x):
        x = np.asarray(x, dtype=np.float64)
        if len(x) < win:
            return np.zeros(0)
        csum = np.concatenate([[0.0], np.cumsum(x * x)])
        starts = np.arange(0, len(x) - win + 1, hop)
        rms = np.sqrt((csum[starts + win] - csum[starts]) / win)
        return np.log(rms + 1e-4)

    tpl = envelope(template)
    a = (tpl - tpl.mean()) / (tpl.std() + 1e-9)
    span = len(template) + int(round(sr * max_delay_ms / 1000.0))
    rec = np.asarray(recorded, dtype=np.float64)
    out = []
    for index, onset in enumerate(onsets):
        env = envelope(rec[onset:onset + span])
        best, lag = -1.0, 0
        for shift in range(0, len(env) - len(tpl) + 1):
            b = env[shift:shift + len(tpl)]
            s = b.std()
            if s < 1e-9:
                continue
            c = float(np.dot(a, (b - b.mean()) / s) / len(tpl))
            if c > best:
                best, lag = c, shift
        entry = {"pulse_index": index, "onset_sample": onset, "confidence": best, "method": "speech_envelope_xcorr_5ms"}
        if best >= threshold:
            entry["delay_ms"] = lag * hop * 1000.0 / sr
            entry["delay_samples"] = lag * hop
        else:
            entry["missing"] = True
        out.append(entry)
    return out


def _run_capture(args, analysis) -> int:
    if not args.input_device or not args.output_device:
        raise ValueError("--input-device and --output-device are required for capture (omit --dry-run)")
    try:
        import numpy as np
        import sounddevice as sd
    except ImportError as exc:
        print(
            "sounddevice 與 numpy 為實際錄放所需，本 repo 不自動安裝。"
            f" ({exc})",
            file=sys.stderr,
        )
        return 3

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.signal == "speech":
        ref, onsets, template, pulse_len = _build_speech_train(args)
    else:
        ref, onsets, template, pulse_len = analysis.build_pulse_train(
            args.signal,
            args.sample_rate,
            pulse_count=args.pulses,
            interval_ms=args.interval_ms,
        )
    _validate_timing(args, pulse_len)
    duration = (len(ref) + args.sample_rate) / args.sample_rate
    hostapi_index = None
    if args.host_api:
        hostapis = [h["name"] for h in sd.query_hostapis()]
        if args.host_api not in hostapis:
            raise ValueError(f"unknown host API {args.host_api!r}; available: {hostapis}")
        hostapi_index = hostapis.index(args.host_api)
    out_idx, out_name = _resolve_device(sd.query_devices, args.output_device, "output", hostapi_index)
    in_idx, in_name = _resolve_device(sd.query_devices, args.input_device, "input", hostapi_index)
    extra = None
    if args.host_api == "Windows WASAPI":
        # 與 services/engines/rvc_runtime.wasapi_settings 同規則，baseline 與 engine 同條件：
        # AUTOCONVERT=1 讓 shared mode 轉換取樣率；EXCLUSIVE_INPUT 片段符合的 capture 用 exclusive。
        extra = (_wasapi_extra(sd, in_name, "input"), _wasapi_extra(sd, out_name, "output"))
        if extra == (None, None):
            extra = None

    # 播放後補 max_delay + 一個脈衝長度的靜音，否則最後一個脈衝的延遲回應會被錄音長度截掉。
    tail = np.zeros(int(round(args.sample_rate * args.max_delay_ms / 1000.0)) + pulse_len, dtype=np.float32)
    playback = np.concatenate([np.asarray(ref, dtype=np.float32), tail])
    recorded = sd.playrec(
        playback,
        args.sample_rate,
        input_mapping=[1],
        output_mapping=[1],
        device=(in_idx, out_idx),
        blocking=True,
        extra_settings=extra,
        dtype="float32",
    )
    rec_mono = recorded.reshape(-1) if recorded.ndim > 1 else recorded
    analysis.write_wav_pcm16(out_dir / "reference.wav", ref, args.sample_rate)
    analysis.write_wav_float32(out_dir / "recorded.wav", rec_mono.tolist(), args.sample_rate)
    meta = {
        "sample_rate": args.sample_rate,
        "pulse_onsets": onsets,
        "pulse_len": pulse_len,
        "template": template,
    }
    (out_dir / "pulses.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    mode = "loopback_baseline" if args.mode == "loopback" else "through_engine"
    per_pulse = _estimate_speech_delays(
        rec_mono, onsets, template, args.sample_rate, args.max_delay_ms
    ) if args.signal == "speech" else analysis.estimate_delays(
        ref,
        rec_mono.tolist(),
        args.sample_rate,
        onsets,
        pulse_len,
        template=template,
        max_delay_ms=args.max_delay_ms,
    )
    summary = analysis.summarize(per_pulse)
    extra: dict[str, Any] = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "capture_seconds": duration,
    }
    baseline_summary = None
    if args.baseline_report:
        baseline = json.loads(Path(args.baseline_report).read_text(encoding="utf-8"))
        baseline_summary = baseline.get("summary", baseline)
    report = analysis.build_report(
        mode,
        sample_rate=args.sample_rate,
        per_pulse=per_pulse,
        summary=summary,
        input_device=in_name,
        output_device=out_name,
        host_api=args.host_api or "",
        baseline_summary=baseline_summary,
        extra=extra,
    )
    (out_dir / "e2e-latency-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _print_one_line_summary(report)
    return 0 if report["target_verdict"] in ("PASS", "WAITING") else 0


def _wasapi_extra(sd, name: str, kind: str):
    fragments = [part.strip().lower() for part in os.environ.get("AETHERTUNE_WASAPI_EXCLUSIVE_INPUT", "").split(";") if part.strip()]
    if kind == "input" and any(part in str(name).lower() for part in fragments):
        return sd.WasapiSettings(exclusive=True)
    if os.environ.get("AETHERTUNE_WASAPI_AUTOCONVERT") == "1":
        return sd.WasapiSettings(auto_convert=True)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="E2E latency bench (pulse train playrec)")
    parser.add_argument("--mode", choices=["loopback", "engine"], default="loopback")
    parser.add_argument("--output-device", default=None)
    parser.add_argument("--input-device", default=None)
    parser.add_argument("--host-api", default="")
    parser.add_argument("--sample-rate", type=int, default=48000)
    parser.add_argument("--pulses", type=int, default=8)
    parser.add_argument("--interval-ms", type=float, default=1000.0)
    parser.add_argument("--max-delay-ms", type=float, default=900.0)
    parser.add_argument("--signal", choices=["click", "chirp", "speech"], default="chirp")
    parser.add_argument("--speech-wav", type=Path, default=ROOT / "dataset" / "reference-voices" / "voice-female-f1.wav",
                        help="speech 訊號來源（只用於實機 capture）")
    parser.add_argument("--speech-ms", type=float, default=400.0)
    parser.add_argument("--blocksize", type=int, default=0)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "artifacts" / "e2e-latency")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--self-test", action="store_true", help="synthetic capture (stdlib analysis path; no sounddevice)")
    parser.add_argument("--self-test-delay-ms", type=float, default=180.0)
    parser.add_argument("--baseline-report", type=Path)
    args = parser.parse_args()

    analysis = _load_analysis()
    if args.self_test:
        if args.dry_run:
            print("--self-test cannot be combined with --dry-run", file=sys.stderr)
            return 2
        return _run_self_test(args, analysis)
    if args.dry_run:
        return _dry_run(args, analysis)
    try:
        return _run_capture(args, analysis)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())