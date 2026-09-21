"""Shared signal gate for locally generated WAV artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf


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
    if not bool(np.isfinite(values).all()):
        raise ValueError(f"output WAV contains non-finite samples: {path}")
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
