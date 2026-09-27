"""Validate and hash ordinary PCM WAV artifacts using only the Python standard library."""

from __future__ import annotations

import hashlib
import wave
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_wav(path: Path) -> dict[str, Any]:
    """Return actual WAV identity and signal-presence metrics; reject unsupported data."""

    path = path.expanduser().resolve()
    if not path.is_file() or path.stat().st_size <= 44:
        raise ValueError(f"WAV artifact is missing or too small: {path}")
    try:
        with wave.open(str(path), "rb") as audio:
            channels = audio.getnchannels()
            sample_rate = audio.getframerate()
            frames = audio.getnframes()
            sample_width = audio.getsampwidth()
            compression = audio.getcomptype()
            if compression != "NONE":
                raise ValueError(f"compressed WAV is not accepted: {compression}")
            if channels <= 0 or sample_rate <= 0 or frames <= 0:
                raise ValueError("WAV must have channels, sample rate, and at least one frame")
            if sample_width not in (1, 2, 3, 4):
                raise ValueError(f"unsupported PCM sample width: {sample_width} bytes")
            non_zero = False
            bytes_remaining = frames * channels * sample_width
            while bytes_remaining:
                frame_bytes = audio.readframes(max(1, min(16384, bytes_remaining // (channels * sample_width))))
                if not frame_bytes:
                    break
                bytes_remaining -= len(frame_bytes)
                if not non_zero:
                    if sample_width == 1:
                        # 8-bit PCM uses unsigned samples, with 128 representing silence.
                        non_zero = any(value != 128 for value in frame_bytes)
                    else:
                        # Signed PCM zero has an all-zero representation at widths 16/24/32.
                        non_zero = any(frame_bytes)
            if bytes_remaining > 0:
                raise ValueError("WAV ended before the declared number of frames")
    except (OSError, EOFError, wave.Error) as exc:
        raise ValueError(f"cannot read a supported PCM WAV: {exc}") from exc

    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "sample_rate_hz": sample_rate,
        "channels": channels,
        "frames": frames,
        "duration_seconds": frames / sample_rate,
        "pcm_sample_width_bytes": sample_width,
        "finite": True,
        "non_zero": non_zero,
    }
