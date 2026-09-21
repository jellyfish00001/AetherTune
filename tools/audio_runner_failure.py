"""Dependency-free output cleanup and failure manifest helpers for TTS runners."""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

OUTPUT_OPTION_NAMES: tuple[str, ...] = ("--output", "--out", "--outp", "--o")


def nonempty_output_path(value: str) -> Path:
    """Shared argparse type: reject an empty path before any filesystem work."""

    if not value:
        raise argparse.ArgumentTypeError("output path 不能為空")
    return Path(value)


def output_from_argv(argv: list[str]) -> Path | None:
    """Mirror argparse's output option scan before parser/import failures.

    The runners expose a fixed alias set and disable implicit argparse
    abbreviation.  argparse uses the last occurrence, so this bootstrap scan
    must do the same.  A following option, empty equals value, or option after
    ``--`` is not treated as a path.
    """

    before_terminator = argv[: argv.index("--")] if "--" in argv else argv
    if "--help" in before_terminator or "-h" in before_terminator:
        return None
    output: Path | None = None
    for index, value in enumerate(argv):
        if value == "--":
            break
        if value in OUTPUT_OPTION_NAMES:
            if index + 1 < len(argv) and not argv[index + 1].startswith("-"):
                candidate = argv[index + 1]
                if not candidate:
                    # Keep the parser in charge of reporting the invalid value.
                    # Returning no cleanup target also prevents a later alias
                    # from deleting stale output before argparse rejects this
                    # empty separated value.
                    return None
                output = Path(candidate)
            else:
                return None
        elif any(value.startswith(f"{name}=") for name in OUTPUT_OPTION_NAMES):
            candidate = value.split("=", 1)[1]
            if not candidate:
                return None
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
