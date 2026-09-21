"""Shared signal gate for locally generated WAV artifacts."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf


def ensure_finite_samples(values: Any, label: str = "audio") -> np.ndarray:
    """Reject NaN/Infinity before a lossy PCM encoder can hide the error."""

    array = np.asarray(values, dtype=np.float64)
    if array.size == 0:
        raise ValueError(f"{label} has no samples")
    if not bool(np.isfinite(array).all()):
        raise ValueError(f"{label} contains non-finite samples")
    return array


def clear_stale_outputs(output: Path) -> Path:
    """Remove only the requested output and manifest before a new run."""

    output.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = output.with_suffix(".json")
    for stale in (output, manifest_path):
        if stale.exists():
            if not stale.is_file():
                raise IsADirectoryError(stale)
            stale.unlink()
    return manifest_path


def write_failure_manifest(output: Path, backend: str, exc: BaseException) -> None:
    """Persist an explicit FAIL state when inference cannot produce a valid WAV."""

    payload = {
        "status": "FAIL",
        "backend": backend,
        "error": f"{type(exc).__name__}: {exc}",
        "output": {"path": str(output)},
        "run_id": uuid.uuid4().hex,
    }
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.with_suffix(".json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        # Preserve the original inference error; the caller still receives a non-zero exit.
        pass


def validate_wav_file(
    path: Path,
    *,
    expected_sample_rate: int | None = None,
    min_peak: float = 1e-5,
) -> dict[str, Any]:
    """Validate a generated WAV before a runner writes a PASS manifest."""

    if not path.is_file() or path.stat().st_size <= 0:
        raise ValueError(f"output WAV is missing or empty: {path}")
    with sf.SoundFile(str(path)) as audio_file:
        sample_rate = int(audio_file.samplerate)
        frames = int(len(audio_file))
        channels = int(audio_file.channels)
        values = np.asarray(audio_file.read(dtype="float32", always_2d=True), dtype=np.float64)
    if sample_rate <= 0 or (expected_sample_rate is not None and sample_rate != expected_sample_rate):
        raise ValueError(
            f"output WAV has unexpected sample rate: actual={sample_rate} expected={expected_sample_rate}"
        )
    if frames <= 0 or channels <= 0 or values.size == 0:
        raise ValueError(f"output WAV has no audio frames: {path}")
    ensure_finite_samples(values, f"output WAV {path}")
    peak = float(np.max(np.abs(values)))
    rms = float(np.sqrt(np.mean(np.square(values))))
    if peak <= min_peak:
        raise ValueError(f"output WAV is effectively silent: peak={peak:.9g}")
    return {
        "sample_rate": sample_rate,
        "frames": frames,
        "channels": channels,
        "duration_sec": frames / sample_rate,
        "peak": peak,
        "rms": rms,
    }
