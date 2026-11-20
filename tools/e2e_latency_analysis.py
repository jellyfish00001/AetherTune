"""E2E latency analysis via pulse-train cross-correlation; stdlib core."""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import struct
import wave
from pathlib import Path
from typing import Any, Literal

SCHEMA_ID = "aethertune-e2e-latency/v1"
DEFAULT_CONFIDENCE_THRESHOLD = 0.35
PULSE_SEARCH_SLACK_MS = 45.0
RESEARCH_TARGET_MS = {"min": 100, "max": 300}


def generate_click_pulse(sample_rate: int, width_ms: float = 2.0) -> list[float]:
    n = max(3, int(sample_rate * width_ms / 1000.0))
    out = [0.0] * n
    mid = n // 2
    out[mid] = 1.0
    for i in range(mid + 1, n):
        out[i] = 0.35 * math.exp(-(i - mid) / max(1.0, n / 6.0))
    peak = max(abs(x) for x in out) or 1.0
    return [x / peak for x in out]


def generate_chirp_pulse(sample_rate: int, duration_ms: float = 25.0, f0: float = 200.0, f1: float = 2000.0) -> list[float]:
    n = max(8, int(sample_rate * duration_ms / 1000.0))
    out: list[float] = []
    for i in range(n):
        t = i / sample_rate
        t1 = n / sample_rate
        if t1 <= 0:
            phase = 0.0
        else:
            k = (f1 / f0) ** (1.0 / t1) if f0 > 0 else 1.0
            phase = 2.0 * math.pi * f0 * (k ** t - 1.0) / math.log(k) if k != 1.0 else 2.0 * math.pi * f0 * t
        w = 0.5 * (1.0 - math.cos(2.0 * math.pi * i / max(1, n - 1)))
        out.append(math.sin(phase) * w)
    peak = max(abs(x) for x in out) or 1.0
    return [x / peak for x in out]


def build_pulse_train(
    signal: Literal["click", "chirp"],
    sample_rate: int,
    *,
    pulse_count: int = 8,
    interval_ms: float = 1000.0,
    start_offset_ms: float = 50.0,
    tail_ms: float = 200.0,
) -> tuple[list[float], list[int], list[float], int]:
    if signal == "click":
        template = generate_click_pulse(sample_rate)
    else:
        template = generate_chirp_pulse(sample_rate)
    pulse_len = len(template)
    interval = int(round(sample_rate * interval_ms / 1000.0))
    start = int(round(sample_rate * start_offset_ms / 1000.0))
    last_onset = start + max(0, pulse_count - 1) * interval
    total = last_onset + pulse_len + int(round(sample_rate * tail_ms / 1000.0))
    buf = [0.0] * total
    onsets: list[int] = []
    for i in range(pulse_count):
        onset = start + i * interval
        onsets.append(onset)
        for j, v in enumerate(template):
            if onset + j < total:
                buf[onset + j] += v
    return buf, onsets, template, pulse_len


def _zero_mean_unit_norm(samples: list[float]) -> tuple[list[float], float]:
    if not samples:
        return [], 0.0
    mean = sum(samples) / len(samples)
    zm = [x - mean for x in samples]
    energy = math.sqrt(sum(x * x for x in zm))
    if energy < 1e-12:
        return zm, 0.0
    return [x / energy for x in zm], energy


def _ncc_prefix_sums(recorded: list[float]) -> tuple[list[float], list[float]]:
    px = [0.0]
    px2 = [0.0]
    for x in recorded:
        px.append(px[-1] + x)
        px2.append(px2[-1] + x * x)
    return px, px2


class _NccSearch:
    """Precomputed template + recorded prefix sums for lag-wise NCC."""

    __slots__ = ("t_norm", "t_len", "px", "px2", "recorded", "inv_len")

    def __init__(self, template: list[float], recorded: list[float]) -> None:
        self.t_norm, _ = _zero_mean_unit_norm(template)
        self.t_len = len(self.t_norm)
        self.recorded = recorded
        self.px, self.px2 = _ncc_prefix_sums(recorded)
        self.inv_len = 1.0 / max(1, self.t_len)

    def score_at(self, anchor: int, lag: int) -> float:
        if not self.t_norm:
            return -1.0
        pos = anchor + lag
        L = self.t_len
        if pos < 0 or pos + L > len(self.recorded):
            return -1.0
        sum_x = self.px[pos + L] - self.px[pos]
        sum_x2 = self.px2[pos + L] - self.px2[pos]
        energy_sq = sum_x2 - sum_x * sum_x * self.inv_len
        if energy_sq < 1e-24:
            return -1.0
        norm = math.sqrt(energy_sq)
        dot = 0.0
        rec = self.recorded
        tn = self.t_norm
        for j in range(L):
            dot += tn[j] * rec[pos + j]
        return dot / norm

    def best_in_range(self, anchor: int, lag_min: int, lag_max: int) -> tuple[int, float]:
        best_lag = lag_min
        best = -1.0
        for lag in range(lag_min, lag_max + 1):
            score = self.score_at(anchor, lag)
            if score > best:
                best = score
                best_lag = lag
        return best_lag, best

    def parabolic_subsample(self, anchor: int, best_lag: int, lag_min: int, lag_max: int, y0: float) -> float:
        sub = float(best_lag)
        if lag_min < best_lag < lag_max:
            ym = self.score_at(anchor, best_lag - 1)
            yp = self.score_at(anchor, best_lag + 1)
            denom = ym - 2.0 * y0 + yp
            if abs(denom) > 1e-12:
                delta = 0.5 * (ym - yp) / denom
                delta = max(-0.5, min(0.5, delta))
                sub = best_lag + delta
        return sub


def _ncc_peak_stdlib(template: list[float], recorded: list[float], lag_min: int, lag_max: int, anchor: int) -> tuple[float, float]:
    """Return (best_lag_fractional, confidence) searching anchor+lag."""
    search = _NccSearch(template, recorded)
    if not search.t_norm:
        return float(anchor + lag_min), 0.0
    best_lag, best = search.best_in_range(anchor, lag_min, lag_max)
    if best < 0:
        return float(anchor + lag_min), 0.0
    sub = search.parabolic_subsample(anchor, best_lag, lag_min, lag_max, best)
    return float(anchor + sub), float(best)


def _ncc_peak_numpy(template: list[float], recorded: list[float], lag_min: int, lag_max: int, anchor: int) -> tuple[float, float]:
    import numpy as np

    t_norm, _ = _zero_mean_unit_norm(template)
    L = len(t_norm)
    if L == 0:
        return float(anchor + lag_min), 0.0
    rec = np.asarray(recorded, dtype=np.float64)
    tn = np.asarray(t_norm, dtype=np.float64)
    px = np.concatenate(([0.0], np.cumsum(rec)))
    px2 = np.concatenate(([0.0], np.cumsum(rec * rec)))
    best_lag = lag_min
    best = -1.0
    inv_len = 1.0 / L
    for lag in range(lag_min, lag_max + 1):
        pos = anchor + lag
        if pos < 0 or pos + L > len(rec):
            continue
        sum_x = px[pos + L] - px[pos]
        sum_x2 = px2[pos + L] - px2[pos]
        mean = sum_x * inv_len
        energy_sq = sum_x2 - sum_x * sum_x * inv_len
        if energy_sq < 1e-24:
            continue
        norm = math.sqrt(float(energy_sq))
        dot = float(np.dot(tn, rec[pos : pos + L]))
        score = dot / norm
        if score > best:
            best = score
            best_lag = lag
    if best < 0:
        return float(anchor + lag_min), 0.0
    sub = float(best_lag)
    if lag_min < best_lag < lag_max:

        def corr_at(lag: int) -> float:
            pos = anchor + lag
            if pos < 0 or pos + L > len(rec):
                return -1.0
            sum_x = px[pos + L] - px[pos]
            sum_x2 = px2[pos + L] - px2[pos]
            mean = sum_x * inv_len
            energy_sq = sum_x2 - sum_x * sum_x * inv_len
            if energy_sq < 1e-24:
                return -1.0
            norm = math.sqrt(float(energy_sq))
            dot = float(np.dot(tn, rec[pos : pos + L]))
            return dot / norm

        ym = corr_at(best_lag - 1)
        y0 = best
        yp = corr_at(best_lag + 1)
        denom = ym - 2.0 * y0 + yp
        if abs(denom) > 1e-12:
            delta = 0.5 * (ym - yp) / denom
            delta = max(-0.5, min(0.5, delta))
            sub = best_lag + delta
    return float(anchor + sub), float(best)


def _ncc_peak(
    template: list[float],
    recorded: list[float],
    lag_min: int,
    lag_max: int,
    anchor: int,
    *,
    use_numpy: bool = False,
) -> tuple[float, float]:
    if use_numpy:
        try:
            return _ncc_peak_numpy(template, recorded, lag_min, lag_max, anchor)
        except ImportError:
            pass
    return _ncc_peak_stdlib(template, recorded, lag_min, lag_max, anchor)


def estimate_delays(
    reference: list[float],
    recorded: list[float],
    sample_rate: int,
    pulse_onsets: list[int],
    pulse_len: int,
    *,
    max_delay_ms: float = 900.0,
    min_delay_ms: float = 0.0,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    template: list[float] | None = None,
    interval_ms: float | None = None,
) -> list[dict[str, Any]]:
    pulse_template = (
        template
        if template is not None
        else reference[pulse_onsets[0] : pulse_onsets[0] + pulse_len]
        if pulse_onsets
        else []
    )
    if interval_ms is None and len(pulse_onsets) >= 2:
        interval_ms = (pulse_onsets[1] - pulse_onsets[0]) * 1000.0 / sample_rate
    pulse_len_ms = pulse_len * 1000.0 / sample_rate
    hint_ms: float | None = None
    hints: list[float] = []
    results: list[dict[str, Any]] = []
    pulse0_detected = False
    for idx, onset in enumerate(pulse_onsets):
        if idx == 0:
            local_min = min_delay_ms
            local_max = max_delay_ms
        elif hint_ms is not None:
            local_min = max(min_delay_ms, hint_ms - PULSE_SEARCH_SLACK_MS)
            local_max = min(max_delay_ms, hint_ms + PULSE_SEARCH_SLACK_MS)
        else:
            local_min = min_delay_ms
            local_max = max_delay_ms
        lag_min = int(math.floor(local_min * sample_rate / 1000.0))
        lag_max = int(math.ceil(local_max * sample_rate / 1000.0))
        peak_pos, conf = _ncc_peak(pulse_template, recorded, lag_min, lag_max, onset)
        delay_ms = (peak_pos - onset) * 1000.0 / sample_rate
        missing = conf < confidence_threshold
        if not missing and hint_ms is not None and abs(delay_ms - hint_ms) > PULSE_SEARCH_SLACK_MS:
            missing = True
        row: dict[str, Any] = {
            "pulse_index": idx,
            "onset_sample": onset,
            "confidence": conf,
            "missing": missing,
        }
        if idx > 0 and not pulse0_detected and interval_ms is not None and interval_ms <= max_delay_ms + pulse_len_ms:
            row["alias_risk"] = True
        if not missing:
            row["delay_ms"] = delay_ms
            hints.append(delay_ms)
            if idx == 0:
                pulse0_detected = True
            if hint_ms is None and len(hints) >= 1:
                hint_ms = hints[0]
            elif len(hints) >= 2:
                ordered = sorted(hints)
                hint_ms = ordered[len(ordered) // 2]
        results.append(row)
    return results


def _percentile_linear(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * (p / 100.0)
    lo = int(rank)
    hi = min(lo + 1, len(ordered) - 1)
    frac = rank - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def summarize(delays: list[dict[str, Any]]) -> dict[str, Any]:
    detected = [float(d["delay_ms"]) for d in delays if not d.get("missing") and "delay_ms" in d]
    missing = sum(1 for d in delays if d.get("missing"))
    summary: dict[str, Any] = {
        "count": len(delays),
        "missing": missing,
        "detected": len(detected),
    }
    if any(d.get("alias_risk") for d in delays):
        summary["alias_risk"] = True
    if detected:
        summary.update(
            min_ms=min(detected),
            max_ms=max(detected),
            mean_ms=statistics.fmean(detected),
            p50_ms=_percentile_linear(detected, 50),
            p95_ms=_percentile_linear(detected, 95),
            jitter_ms=statistics.pstdev(detected) if len(detected) > 1 else 0.0,
            e2e_first_packet_ms=detected[0],
            e2e_p50_ms=_percentile_linear(detected, 50),
            e2e_p95_ms=_percentile_linear(detected, 95),
        )
    else:
        summary.update(
            min_ms=None,
            max_ms=None,
            mean_ms=None,
            p50_ms=None,
            p95_ms=None,
            jitter_ms=None,
            e2e_first_packet_ms=None,
            e2e_p50_ms=None,
            e2e_p95_ms=None,
        )
    return summary


def target_verdict(summary: dict[str, Any]) -> str:
    if summary.get("detected", 0) == 0:
        return "BLOCKED"
    if summary.get("missing", 0) > 0:
        return "WAITING"
    p95 = summary.get("p95_ms")
    if p95 is None:
        return "WAITING"
    if p95 <= RESEARCH_TARGET_MS["max"] and summary.get("detected") == summary.get("count"):
        return "PASS"
    return "WAITING"


def compare_engine_baseline(engine_summary: dict[str, Any], baseline_summary: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in ("p50_ms", "p95_ms", "mean_ms", "e2e_first_packet_ms"):
        ev = engine_summary.get(key)
        bv = baseline_summary.get(key)
        if isinstance(ev, (int, float)) and isinstance(bv, (int, float)):
            out[f"engine_minus_baseline_{key}"] = float(ev) - float(bv)
    if "engine_minus_baseline_p95_ms" in out:
        out["engine_minus_baseline_ms"] = out["engine_minus_baseline_p95_ms"]
    return out


def build_report(
    mode: Literal["loopback_baseline", "through_engine"],
    *,
    sample_rate: int,
    per_pulse: list[dict[str, Any]],
    summary: dict[str, Any] | None = None,
    input_device: str = "",
    output_device: str = "",
    host_api: str = "",
    baseline_summary: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = summary or summarize(per_pulse)
    report: dict[str, Any] = {
        "schema": SCHEMA_ID,
        "mode": mode,
        "sample_rate": sample_rate,
        "input_device": input_device,
        "output_device": output_device,
        "host_api": host_api,
        "per_pulse": per_pulse,
        "summary": summary,
        "target_ms": dict(RESEARCH_TARGET_MS),
        "target_verdict": target_verdict(summary),
    }
    if baseline_summary is not None:
        report["baseline_summary"] = baseline_summary
        report["compare"] = compare_engine_baseline(summary, baseline_summary)
    if extra:
        report.update(extra)
    return report


def _read_wav_frames(path: Path) -> tuple[list[float], int, int]:
    """讀 16-bit PCM 或 32-bit float WAV（含 WAVE_FORMAT_IEEE_FLOAT=3；stdlib wave 讀不了 format 3）。"""
    raw = Path(path).read_bytes()
    if raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise ValueError(f"not a RIFF/WAVE file: {path}")
    pos, fmt, data = 12, None, None
    while pos + 8 <= len(raw):
        chunk_id = raw[pos : pos + 4]
        size = struct.unpack("<I", raw[pos + 4 : pos + 8])[0]
        body = raw[pos + 8 : pos + 8 + size]
        if chunk_id == b"fmt ":
            fmt = body
        elif chunk_id == b"data":
            data = body
        pos += 8 + size + (size & 1)
    if fmt is None or data is None:
        raise ValueError(f"WAV missing fmt/data chunk: {path}")
    tag, channels, rate = struct.unpack("<HHI", fmt[:8])
    width = struct.unpack("<H", fmt[14:16])[0] // 8
    if tag == 0xFFFE and len(fmt) >= 26:  # WAVE_FORMAT_EXTENSIBLE：SubFormat 前 2 bytes 即 format tag
        tag = struct.unpack("<H", fmt[24:26])[0]
    if width == 2 and tag == 1:
        count = len(data) // 2
        ints = struct.unpack(f"<{count}h", data[: count * 2])
        mono = [sum(ints[i : i + channels]) / (32768.0 * channels) for i in range(0, count, channels)]
    elif width == 4 and tag in (1, 3):
        # tag 1＋32-bit：舊版 write_wav_float32 把 float 資料標成 PCM，仍以 float 讀以相容舊證據。
        count = len(data) // 4
        floats = struct.unpack(f"<{count}f", data[: count * 4])
        mono = [sum(floats[i : i + channels]) / channels for i in range(0, count, channels)]
    else:
        raise ValueError(f"unsupported WAV format tag={tag} width={width}")
    return mono, rate, channels


def read_wav_mono(path: Path) -> tuple[list[float], int]:
    samples, rate, _ch = _read_wav_frames(path)
    return samples, rate


def write_wav_pcm16(path: Path, samples: list[float], sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    clipped = [max(-1.0, min(1.0, x)) for x in samples]
    pcm = b"".join(struct.pack("<h", int(round(x * 32767.0))) for x in clipped)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)


def write_wav_float32(path: Path, samples: list[float], sample_rate: int) -> None:
    """32-bit IEEE float WAV（format tag 3＋fact chunk）。

    舊版用 stdlib wave 寫成 PCM 標頭，soundfile／DAW 會把 float 位元當整數讀成雜訊。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    data = b"".join(struct.pack("<f", float(x)) for x in samples)
    frames = len(data) // 4
    fmt = struct.pack("<HHIIHH", 3, 1, sample_rate, sample_rate * 4, 4, 32)
    body = (
        b"WAVE"
        + b"fmt " + struct.pack("<I", len(fmt)) + fmt
        + b"fact" + struct.pack("<I", 4) + struct.pack("<I", frames)
        + b"data" + struct.pack("<I", len(data)) + data
    )
    path.write_bytes(b"RIFF" + struct.pack("<I", len(body)) + body)


def apply_fractional_delay(samples: list[float], delay_samples: float) -> list[float]:
    if delay_samples <= 0:
        return list(samples)
    pad = int(math.ceil(delay_samples)) + 2
    out: list[float] = [0.0] * (len(samples) + pad)
    for i in range(len(out)):
        src = i - delay_samples
        if src < 0:
            continue
        if src >= len(samples):
            continue
        i0 = int(math.floor(src))
        frac = src - i0
        if i0 + 1 < len(samples):
            out[i] = samples[i0] * (1.0 - frac) + samples[i0 + 1] * frac
        elif i0 < len(samples):
            out[i] = samples[i0]
    return out


def inject_noise(samples: list[float], snr_db: float, rng: random.Random) -> list[float]:
    signal_power = sum(x * x for x in samples) / max(1, len(samples))
    if signal_power < 1e-18:
        return list(samples)
    noise_power = signal_power / (10.0 ** (snr_db / 10.0))
    scale = math.sqrt(noise_power)
    return [x + rng.gauss(0.0, scale) for x in samples]


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Offline E2E latency re-analysis from WAV files")
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--recorded", type=Path, required=True)
    parser.add_argument("--pulses-json", type=Path, required=True, help="JSON with onsets, pulse_len, sample_rate")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--mode", choices=["loopback_baseline", "through_engine"], default="loopback_baseline")
    args = parser.parse_args()
    meta = json.loads(args.pulses_json.read_text(encoding="utf-8"))
    ref, ref_rate = read_wav_mono(args.reference)
    rec, rec_rate = read_wav_mono(args.recorded)
    sr = int(meta.get("sample_rate", ref_rate))
    if ref_rate != sr or rec_rate != sr:
        raise SystemExit(f"sample rate mismatch: ref={ref_rate} rec={rec_rate} expected={sr}")
    onsets = [int(x) for x in meta["pulse_onsets"]]
    pulse_len = int(meta["pulse_len"])
    template = meta.get("template")
    if template is not None:
        template = [float(x) for x in template]
    per_pulse = estimate_delays(ref, rec, sr, onsets, pulse_len, template=template)
    report = build_report(args.mode, sample_rate=sr, per_pulse=per_pulse)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())