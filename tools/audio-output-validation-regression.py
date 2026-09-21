"""Regression tests for generated WAV signal validation."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from audio_output_validation import validate_wav_file


with tempfile.TemporaryDirectory(prefix="aethertune-audio-gate-") as temp_dir:
    root = Path(temp_dir)
    valid = root / "valid.wav"
    silent = root / "silent.wav"
    nonfinite = root / "nonfinite.wav"
    sf.write(valid, np.array([0.0, 0.1, -0.2, 0.05], dtype=np.float32), 24000)
    sf.write(silent, np.zeros(4, dtype=np.float32), 24000)
    sf.write(nonfinite, np.array([np.nan, 0.0], dtype=np.float32), 24000, subtype="FLOAT")

    assert validate_wav_file(valid, expected_sample_rate=24000)["frames"] == 4
    for invalid in (silent, nonfinite):
        try:
            validate_wav_file(invalid, expected_sample_rate=24000)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid WAV accepted: {invalid.name}")
print("PASS generated WAV validation regression")
