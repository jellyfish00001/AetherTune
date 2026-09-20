"""Offline Faster-Whisper transcription with a JSON evidence manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from faster_whisper import WhisperModel


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Transcribe one local audio file")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--model", default="small")
    parser.add_argument("--language")
    args = parser.parse_args()
    if not args.input.is_file():
        raise FileNotFoundError(args.input)

    started = time.perf_counter()
    model = WhisperModel(args.model, device="cpu", compute_type="int8")
    segments, info = model.transcribe(
        str(args.input),
        language=args.language,
        beam_size=5,
        vad_filter=True,
    )
    materialized = list(segments)
    text = "".join(segment.text for segment in materialized).strip()
    elapsed = time.perf_counter() - started
    args.output.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "status": "PASS" if text else "WAITING",
        "backend": "faster-whisper",
        "model": args.model,
        "input": {"path": str(args.input), "sha256": sha256(args.input)},
        "language": info.language,
        "language_probability": info.language_probability,
        "duration_seconds": info.duration,
        "text": text,
        "segments": [
            {"start": item.start, "end": item.end, "text": item.text}
            for item in materialized
        ],
        "elapsed_seconds": elapsed,
        "manual_review_required": True,
    }
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if text else 2


if __name__ == "__main__":
    raise SystemExit(main())
