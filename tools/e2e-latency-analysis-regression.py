"""Synthetic regression for e2e_latency_analysis (stdlib only)."""

from __future__ import annotations

import importlib.util
import json
import random
import subprocess
import sys
import tempfile
import time
from pathlib import Path


PATH = Path(__file__).with_name("e2e_latency_analysis.py")
SPEC = importlib.util.spec_from_file_location("e2e_latency_analysis", PATH)
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)

SR = 16000
TOL_MS = 1.0
INTERVAL_MS = 1000.0
MAX_DELAY_MS = 900.0


def _assert_delays(
    signal: str,
    delay_ms: float,
    *,
    fractional: bool = False,
    interval_ms: float = INTERVAL_MS,
    max_delay_ms: float = MAX_DELAY_MS,
) -> None:
    ref, onsets, template, pulse_len = MOD.build_pulse_train(
        signal, SR, pulse_count=6, interval_ms=interval_ms, start_offset_ms=80.0
    )
    delay_samples = delay_ms * SR / 1000.0
    if fractional:
        delay_samples += 0.3
    rec = MOD.apply_fractional_delay(ref, delay_samples)
    rng = random.Random(17)
    rec = MOD.inject_noise(rec, 20.0, rng)
    rec = [x * 0.65 for x in rec]
    estimates = MOD.estimate_delays(
        ref, rec, SR, onsets, pulse_len, template=template, max_delay_ms=max_delay_ms
    )
    for row in estimates:
        assert not row["missing"], row
        assert abs(row["delay_ms"] - delay_ms) <= TOL_MS, (signal, delay_ms, row)


def test_no_old_aliasing_850ms() -> None:
    """With 1000 ms interval, 850 ms delay must not alias to ~150 ms."""
    _assert_delays("chirp", 850.0, interval_ms=1000.0, max_delay_ms=900.0)


def test_numpy_stdlib_agree() -> None:
    try:
        import numpy as np  # noqa: F401
    except ImportError:
        print("SKIP numpy path agreement (numpy not importable)")
        return
    ref, onsets, template, pulse_len = MOD.build_pulse_train("chirp", SR, pulse_count=4, interval_ms=1000.0)
    delay_samples = 600.0 * SR / 1000.0
    rec = MOD.apply_fractional_delay(ref, delay_samples)
    onset = onsets[0]
    lag_min = 0
    lag_max = int(SR * 0.95)
    std_pos, std_conf = MOD._ncc_peak_stdlib(template, rec, lag_min, lag_max, onset)
    np_pos, np_conf = MOD._ncc_peak_numpy(template, rec, lag_min, lag_max, onset)
    std_delay = (std_pos - onset) * 1000.0 / SR
    np_delay = (np_pos - onset) * 1000.0 / SR
    assert abs(std_delay - np_delay) <= 0.05, (std_delay, np_delay, std_conf, np_conf)


def test_missing_pulse() -> None:
    ref, onsets, template, pulse_len = MOD.build_pulse_train("chirp", SR, pulse_count=5, interval_ms=1000.0)
    delay_samples = 120.0 * SR / 1000.0
    rec = MOD.apply_fractional_delay(ref, delay_samples)
    onset = onsets[2]
    start = int(onset + delay_samples) - 4
    end = start + pulse_len + 8
    for i in range(max(0, start), min(len(rec), end)):
        rec[i] = 0.0
    estimates = MOD.estimate_delays(ref, rec, SR, onsets, pulse_len, template=template)
    assert estimates[2]["missing"] is True
    summary = MOD.summarize(estimates)
    assert summary["missing"] >= 1


def test_summarize_percentiles() -> None:
    delays = [
        {"missing": False, "delay_ms": 100.0},
        {"missing": False, "delay_ms": 200.0},
        {"missing": False, "delay_ms": 300.0},
        {"missing": True},
    ]
    summary = MOD.summarize(delays)
    assert summary["count"] == 4
    assert summary["missing"] == 1
    assert summary["p50_ms"] == 200.0
    assert abs(summary["p95_ms"] - 290.0) < 0.01
    assert summary["e2e_first_packet_ms"] == 100.0


def test_compare_and_verdict() -> None:
    engine = MOD.summarize([{"missing": False, "delay_ms": 220.0}, {"missing": False, "delay_ms": 240.0}])
    baseline = MOD.summarize([{"missing": False, "delay_ms": 80.0}, {"missing": False, "delay_ms": 90.0}])
    report_pass = MOD.build_report("through_engine", sample_rate=SR, per_pulse=[], summary=engine, baseline_summary=baseline)
    assert report_pass["compare"]["engine_minus_baseline_ms"] == engine["p95_ms"] - baseline["p95_ms"]
    good = {"count": 4, "missing": 0, "detected": 4, "p95_ms": 250.0}
    bad = {"count": 4, "missing": 0, "detected": 4, "p95_ms": 400.0}
    assert MOD.target_verdict(good) == "PASS"
    assert MOD.target_verdict(bad) != "PASS"
    assert MOD.target_verdict(good) != "LIVE"


def test_wav_roundtrip() -> None:
    ref, onsets, template, pulse_len = MOD.build_pulse_train("click", SR, pulse_count=3, interval_ms=1000.0)
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "a.wav"
        MOD.write_wav_pcm16(wav, ref, SR)
        read_back, rate = MOD.read_wav_mono(wav)
        assert rate == SR
        assert len(read_back) == len(ref)
        estimates = MOD.estimate_delays(ref, read_back, SR, onsets, pulse_len, template=template, max_delay_ms=50.0)
        for row in estimates:
            assert not row["missing"]
            assert abs(row["delay_ms"]) <= TOL_MS


def test_bench_self_test_subprocess() -> None:
    bench = Path(__file__).with_name("e2e-latency-bench.py")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        proc = subprocess.run(
            [sys.executable, str(bench), "--self-test", "--out-dir", str(out), "--self-test-delay-ms", "180"],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        assert proc.returncode == 0, (proc.returncode, proc.stderr, proc.stdout)
        report_path = out / "e2e-latency-report.json"
        assert report_path.is_file(), proc.stdout
        report = json.loads(report_path.read_text(encoding="utf-8"))
        p50 = report["summary"]["p50_ms"]
        assert p50 is not None and abs(float(p50) - 180.0) <= TOL_MS, report["summary"]
        assert "verdict=" in proc.stdout


def main() -> int:
    t0 = time.perf_counter()
    _assert_delays("click", 120.0)
    _assert_delays("chirp", 450.0)
    _assert_delays("chirp", 600.0)
    _assert_delays("chirp", 120.3, fractional=True)
    test_no_old_aliasing_850ms()
    test_numpy_stdlib_agree()
    test_missing_pulse()
    test_summarize_percentiles()
    test_compare_and_verdict()
    test_wav_roundtrip()
    test_bench_self_test_subprocess()
    elapsed = time.perf_counter() - t0
    assert elapsed < 60.0, elapsed
    print(f"PASS e2e latency analysis regression ({elapsed:.2f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())