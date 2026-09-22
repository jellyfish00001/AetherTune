"""Validate AetherTune LIVE_GATE evidence without pretending to run the audio chain."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any


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


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _fail(message: str) -> tuple[str, list[str]]:
    return "BLOCKED", [message]


def classify(record: dict[str, Any]) -> tuple[str, list[str]]:
    missing = sorted(REQUIRED_TOP_LEVEL - record.keys())
    if missing:
        return _fail(f"missing top-level fields: {', '.join(missing)}")
    if record.get("schema_version") != "aethertune-live-gate/v1":
        return _fail("schema_version must be aethertune-live-gate/v1")

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
        return "WAITING", ["output_validation is not a verified finite non-zero PASS artifact"]
    if output.get("status") != "PASS" or output.get("finite") is not True or output.get("non_zero") is not True:
        return "BLOCKED", ["output_validation explicitly failed finite/non-zero validation"]

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
