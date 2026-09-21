"""Dependency-free output cleanup and failure manifest helpers for TTS runners."""

from __future__ import annotations

import json
import uuid
from pathlib import Path


def output_from_argv(argv: list[str]) -> Path | None:
    """Mirror argparse's output option scan before parser/import failures.

    The runners expose ``--output`` and argparse also accepts its unambiguous
    ``--out`` abbreviation.  argparse uses the last occurrence, so this
    bootstrap scan must do the same.  A following option is not treated as a
    path; the parser will report that malformed invocation later.
    """

    if "--help" in argv or "-h" in argv:
        return None
    output: Path | None = None
    option_names = {"--output", "--out"}
    for index, value in enumerate(argv):
        if value in option_names:
            if index + 1 < len(argv) and not argv[index + 1].startswith("-"):
                output = Path(argv[index + 1])
        elif any(value.startswith(f"{name}=") for name in option_names):
            candidate = value.split("=", 1)[1]
            if candidate:
                output = Path(candidate)
    return output


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
