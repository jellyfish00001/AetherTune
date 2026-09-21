"""四種語音後端的 WAV signal-level 批次比較工具。

這個工具只量測可重現的音訊訊號指標，不宣稱 MOS、自然度或聲線相似度。
它適合先抓出解碼失敗、全零、取樣率不一致、過小音量與 clipping，再把
輸出交給人工聽測或正式感知評估。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf


ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def dbfs(value: float) -> float | None:
    return round(20.0 * math.log10(value), 4) if value > 0 else None


def measure(path: Path, backend: str, case: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "backend": backend,
        "case": case,
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "status": "BLOCKED",
    }
    try:
        info = sf.info(str(path))
        audio, sample_rate = sf.read(str(path), always_2d=True, dtype="float32")
        values = np.asarray(audio, dtype=np.float64)
        flattened = values.reshape(-1)
        finite = bool(np.isfinite(values).all())
        frames = int(values.shape[0])
        channels = int(values.shape[1])
        rms = float(np.sqrt(np.mean(np.square(flattened)))) if flattened.size else 0.0
        peak = float(np.max(np.abs(flattened))) if flattened.size else 0.0
        silence_ratio = float(np.mean(np.abs(flattened) < 1e-4)) if flattened.size else 1.0
        clip_ratio = float(np.mean(np.abs(flattened) >= 0.999)) if flattened.size else 0.0
        dc_offset = float(np.mean(flattened)) if flattened.size else 0.0
        valid_signal = finite and frames > 0 and peak > 1e-5
        result.update(
            {
                "status": "PASS" if valid_signal else "BLOCKED",
                "bytes": path.stat().st_size,
                "sample_rate": int(sample_rate),
                "reported_format": info.format,
                "reported_subtype": info.subtype,
                "channels": channels,
                "frames": frames,
                "duration_sec": round(frames / sample_rate, 5) if sample_rate else None,
                "finite": finite,
                "rms": round(rms, 8),
                "rms_dbfs": dbfs(rms),
                "peak": round(peak, 8),
                "peak_dbfs": dbfs(peak),
                "clipping_ratio": round(clip_ratio, 8),
                "silence_ratio": round(silence_ratio, 8),
                "dc_offset": round(dc_offset, 8),
                "sha256": sha256_file(path),
            }
        )
        if valid_signal and (clip_ratio > 0 or silence_ratio > 0.98):
            result["status"] = "DEGRADED"
    except Exception as exc:  # pragma: no cover - the report must retain bad files
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def add_glob(records: list[tuple[str, str, Path]], backend: str, case: str, pattern: str) -> None:
    for path in sorted(ROOT.glob(pattern)):
        if path.is_file() and path.suffix.lower() == ".wav":
            records.append((backend, case, path))


def build_records() -> list[tuple[str, str, Path]]:
    records: list[tuple[str, str, Path]] = []
    add_glob(records, "RVC", "fcpe-gpu-roles", "artifacts/rvc-fcpe-gpu/*.wav")
    add_glob(records, "Seed-VC", "male-to-female", "artifacts/seed-vc/latest-male-to-female/*.wav")
    add_glob(records, "Seed-VC", "female-to-male", "artifacts/seed-vc/latest-female-to-male/*.wav")
    add_glob(records, "CosyVoice2", "clone-male", "artifacts/speech-reconstruction/cosyvoice-clone-male.wav")
    add_glob(records, "CosyVoice2", "clone-female", "artifacts/speech-reconstruction/cosyvoice-clone-female.wav")
    add_glob(records, "Breeze TTS 2", "clone-male", "artifacts/speech-reconstruction/breeze-clone-male.wav")
    add_glob(records, "Breeze TTS 2", "clone-female", "artifacts/speech-reconstruction/breeze-clone-female.wav")
    return records


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["backend"]].append(row)
    summaries = []
    for backend, items in sorted(grouped.items()):
        good = [item for item in items if item.get("status") in {"PASS", "DEGRADED"}]
        blocked = [item for item in items if item.get("status") == "BLOCKED"]
        if blocked:
            status = "BLOCKED"
        elif not good:
            status = "BLOCKED"
        elif any(item.get("status") == "DEGRADED" for item in good):
            status = "DEGRADED"
        else:
            status = "PASS"
        summaries.append(
            {
                "backend": backend,
                "status": status,
                "files": len(items),
                "pass_or_degraded": len(good),
                "blocked": len(blocked),
                "sample_rates": sorted({item.get("sample_rate") for item in good}),
                "durations_sec": [round(float(item["duration_sec"]), 5) for item in good],
                "rms_dbfs": [item.get("rms_dbfs") for item in good],
                "peak_dbfs": [item.get("peak_dbfs") for item in good],
                "clipping_ratio": [item.get("clipping_ratio") for item in good],
            }
        )
    return summaries


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch signal-level WAV comparison for AetherTune backends")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "artifacts" / "audio-quality-comparison")
    args = parser.parse_args()
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    inputs = build_records()
    rows = [measure(path, backend, case) for backend, case, path in inputs]
    summaries = summarize(rows)
    backends = {row["backend"] for row in rows}
    expected = {"RVC", "Seed-VC", "CosyVoice2", "Breeze TTS 2"}
    if not rows or backends != expected or any(row["status"] == "BLOCKED" for row in rows):
        overall = "BLOCKED"
    elif any(row["status"] == "DEGRADED" for row in rows):
        overall = "DEGRADED"
    else:
        overall = "PASS"
    report = {
        "status": overall,
        "measurement_scope": "signal-level WAV decode, volume proxy, sample rate and validity; not MOS or human quality",
        "expected_backends": sorted(expected),
        "observed_backends": sorted(backends),
        "rows": rows,
        "summaries": summaries,
    }
    json_path = output_dir / "audio-quality-comparison.json"
    csv_path = output_dir / "audio-quality-comparison.csv"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    columns = sorted({key for row in rows for key in row})
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"status": overall, "files": len(rows), "json": str(json_path), "csv": str(csv_path), "summaries": summaries}, ensure_ascii=False, indent=2))
    return 0 if overall in {"PASS", "DEGRADED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
