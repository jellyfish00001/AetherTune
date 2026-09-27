"""Validate AetherTune LIVE_GATE evidence without pretending to run the audio chain."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

_HELPERS = Path(__file__).resolve().parent
sys.path.insert(0, str(_HELPERS))
from importlib.util import module_from_spec, spec_from_file_location

_WAV_SPEC = spec_from_file_location("wav_evidence", _HELPERS / "wav-evidence.py")
assert _WAV_SPEC and _WAV_SPEC.loader
_WAV_MODULE = module_from_spec(_WAV_SPEC)
_WAV_SPEC.loader.exec_module(_WAV_MODULE)
validate_wav = _WAV_MODULE.validate_wav
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
PROJECT_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_TOP_LEVEL = {
    "schema_version",
    "run_id",
    "backend_id",
    "route_profile",
    "hardware",
    "capture",
    "timing_ms",
    "continuity",
    "output_validation",
}
REQUIRED_TIMINGS = {
    "capture_to_backend_first_packet_ms",
    "backend_first_packet_ms",
    "postfx_first_packet_ms",
    "routing_first_packet_ms",
    "e2e_first_packet_ms",
    "e2e_p50_ms",
    "e2e_p95_ms",
}
REQUIRED_CAPTURE = {
    "device",
    "host_api",
    "sample_rate_hz",
    "channels",
    "input_wav",
    "input_sha256",
    "reference_wav",
    "reference_sha256",
}
REQUIRED_OUTPUT = {"status", "finite", "non_zero", "output_wav", "wav_sha256"}


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _fail(message: str) -> tuple[str, list[str]]:
    return "BLOCKED", [message]


def _resolve_artifact(value: Any, root: Path) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = Path(value).expanduser()
    return candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()


def _check_wav(path_value: Any, expected_hash: Any, label: str, root: Path) -> tuple[str, str | None]:
    path = _resolve_artifact(path_value, root)
    if path is None:
        return "BLOCKED", f"{label} path is missing or empty"
    if not isinstance(expected_hash, str) or not SHA256_RE.fullmatch(expected_hash):
        return "BLOCKED", f"{label} SHA-256 must be a 64-character hex digest"
    try:
        actual = validate_wav(path)
    except (OSError, ValueError) as exc:
        return "BLOCKED", f"{label} WAV validation failed: {exc}"
    if actual["sha256"].lower() != expected_hash.lower():
        return "BLOCKED", f"{label} SHA-256 does not match the referenced WAV"
    if actual["non_zero"] is not True:
        return "BLOCKED", f"{label} WAV is silent"
    return "PASS", None


def classify(record: dict[str, Any], artifact_root: Path | None = None) -> tuple[str, list[str]]:
    missing = sorted(REQUIRED_TOP_LEVEL - record.keys())
    if missing:
        return _fail(f"missing top-level fields: {', '.join(missing)}")
    if record.get("schema_version") != "aethertune-live-gate/v1":
        return _fail("schema_version must be aethertune-live-gate/v1")
    if not isinstance(record.get("run_id"), str) or not record["run_id"].strip():
        return _fail("run_id must be a non-empty string")
    if not isinstance(record.get("backend_id"), str) or not record["backend_id"].strip():
        return _fail("backend_id must be a non-empty string")

    root = (artifact_root or PROJECT_ROOT).resolve()
    capture = record["capture"]
    if not isinstance(capture, dict):
        return _fail("capture must be an object")
    missing_capture = sorted(REQUIRED_CAPTURE - capture.keys())
    if missing_capture:
        return _fail(f"missing capture fields: {', '.join(missing_capture)}")
    for key in ("device", "host_api"):
        if not isinstance(capture[key], str) or not capture[key].strip():
            return _fail(f"capture.{key} must be a non-empty string")
    for key in ("sample_rate_hz", "channels"):
        if not isinstance(capture[key], int) or isinstance(capture[key], bool) or capture[key] <= 0:
            return _fail(f"capture.{key} must be a positive integer")
    for key, hash_key, label in (
        ("input_wav", "input_sha256", "capture input"),
        ("reference_wav", "reference_sha256", "reference"),
    ):
        status, message = _check_wav(capture[key], capture[hash_key], label, root)
        if status != "PASS":
            return _fail(message or f"{label} validation failed")

    timing = record["timing_ms"]
    if not isinstance(timing, dict):
        return _fail("timing_ms must be an object")
    missing_timing = sorted(REQUIRED_TIMINGS - timing.keys())
    if missing_timing:
        return _fail(f"missing timing fields: {', '.join(missing_timing)}")
    bad_timing = [key for key in REQUIRED_TIMINGS if not _is_number(timing[key]) or timing[key] < 0]
    if bad_timing:
        return _fail(f"timing fields must be finite non-negative numbers: {', '.join(sorted(bad_timing))}")

    continuity = record["continuity"]
    if not isinstance(continuity, dict):
        return _fail("continuity must be an object")
    for key in ("continuous_seconds", "dropouts", "underruns"):
        if key not in continuity:
            return _fail(f"missing continuity field: {key}")
    if not _is_number(continuity["continuous_seconds"]) or continuity["continuous_seconds"] < 0:
        return _fail("continuous_seconds must be a finite non-negative number")
    if any(not isinstance(continuity[key], int) or continuity[key] < 0 for key in ("dropouts", "underruns")):
        return _fail("dropouts and underruns must be non-negative integers")

    output = record["output_validation"]
    if not isinstance(output, dict):
        return _fail("output_validation must be an object")
    if output.get("status") == "WAITING":
        return "WAITING", ["output_validation is not a verified finite non-zero WAV artifact"]
    missing_output = sorted(REQUIRED_OUTPUT - output.keys())
    if missing_output:
        return _fail(f"missing output_validation fields: {', '.join(missing_output)}")
    if output.get("status") != "PASS" or output.get("finite") is not True or output.get("non_zero") is not True:
        return "BLOCKED", ["output_validation explicitly failed finite/non-zero validation"]
    status, message = _check_wav(output["output_wav"], output["wav_sha256"], "routed output", root)
    if status != "PASS":
        return _fail(message or "routed output validation failed")

    first_packet = timing["e2e_first_packet_ms"]
    if first_packet > 5000:
        return "OFFLINE", [f"e2e_first_packet_ms={first_packet:g} exceeds the 5000 ms LIVE budget"]

    warnings: list[str] = []
    if continuity["continuous_seconds"] < 60:
        warnings.append("continuous_seconds is below the 60 s screening evidence target")
    if continuity["dropouts"] or continuity["underruns"]:
        warnings.append("dropouts or underruns are present; this is not a live_candidate")
    if continuity["continuous_seconds"] < 600:
        warnings.append("600 s live_candidate stability evidence is still missing")
    return "LIVE", warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify AetherTune LIVE_GATE evidence")
    parser.add_argument("evidence", type=Path, help="path to a live-gate/v1 JSON evidence file")
    args = parser.parse_args()

    try:
        record = json.loads(args.evidence.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"BLOCKED: evidence file not found: {args.evidence}")
        return 2
    except (OSError, json.JSONDecodeError) as exc:
        print(f"BLOCKED: cannot read evidence: {exc}")
        return 2

    if not isinstance(record, dict):
        print("BLOCKED: evidence root must be a JSON object")
        return 2
    status, messages = classify(record)
    for message in messages:
        print(f"{status}: {message}")
    print(f"classification={status}")
    if status == "BLOCKED":
        return 2
    if status == "WAITING":
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
