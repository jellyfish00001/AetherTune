"""Regression tests for generated WAV signal validation."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from audio_output_validation import (
    clear_stale_outputs,
    ensure_finite_samples,
    validate_wav_file,
    write_failure_manifest,
)


with tempfile.TemporaryDirectory(prefix="aethertune-audio-gate-") as temp_dir:
    root = Path(temp_dir)
    valid = root / "valid.wav"
    silent = root / "silent.wav"
    nonfinite = root / "nonfinite.wav"
    infinity = root / "infinity.wav"
    empty = root / "empty.wav"
    zero_frames = root / "zero-frames.wav"
    wrong_rate = root / "wrong-rate.wav"
    pcm16 = root / "pcm16.wav"
    sf.write(valid, np.array([0.0, 0.1, -0.2, 0.05], dtype=np.float32), 24000)
    sf.write(silent, np.zeros(4, dtype=np.float32), 24000)
    sf.write(nonfinite, np.array([np.nan, 0.0], dtype=np.float32), 24000, subtype="FLOAT")
    sf.write(infinity, np.array([np.inf, 0.0], dtype=np.float32), 24000, subtype="FLOAT")
    empty.write_bytes(b"")
    with sf.SoundFile(zero_frames, mode="w", samplerate=24000, channels=1, subtype="PCM_16"):
        pass
    sf.write(wrong_rate, np.array([0.1, -0.1], dtype=np.float32), 16000)
    # PCM16 encoding can turn NaN into a finite value; the pre-encode helper must catch it first.
    sf.write(pcm16, np.array([np.nan, 0.1], dtype=np.float32), 24000, subtype="PCM_16")

    assert validate_wav_file(valid, expected_sample_rate=24000)["frames"] == 4
    for invalid in (silent, nonfinite, infinity, empty, zero_frames):
        try:
            validate_wav_file(invalid, expected_sample_rate=24000)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid WAV accepted: {invalid.name}")
    try:
        validate_wav_file(wrong_rate, expected_sample_rate=24000)
    except ValueError:
        pass
    else:
        raise AssertionError("wrong sample rate accepted")
    assert validate_wav_file(pcm16, expected_sample_rate=24000)["frames"] == 2
    for invalid in (np.array([np.nan, 0.1]), np.array([np.inf, 0.1])):
        try:
            ensure_finite_samples(invalid, "raw chunk")
        except ValueError:
            pass
        else:
            raise AssertionError("non-finite raw chunk accepted")

    stale_output = root / "stale.wav"
    stale_manifest = stale_output.with_suffix(".json")
    stale_output.write_bytes(b"old-output")
    stale_manifest.write_text('{"status":"PASS"}', encoding="utf-8")
    assert clear_stale_outputs(stale_output) == stale_manifest
    assert not stale_output.exists() and not stale_manifest.exists()
    write_failure_manifest(stale_output, "test-backend", RuntimeError("synthetic failure"))
    failure = json.loads(stale_manifest.read_text(encoding="utf-8"))
    assert failure["status"] == "FAIL" and failure["backend"] == "test-backend"
print("PASS generated WAV validation regression")
