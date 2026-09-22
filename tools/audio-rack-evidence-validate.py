"""Validate an AetherTune audio-rack/evidence-v1 JSON record.

這個 validator 只分類既有 evidence，不會啟動音訊裝置、建立 WAV 或把
缺少的欄位補成 PASS。它與 LIVE_GATE validator 分開，因為 rack A/B 的
delta latency 與 plugin 狀態需要額外記錄。
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any


REQUIRED = {
    "schema_version",
    "run_id",
    "backend_id",
    "route_profile",
    "rack_mode",
    "timing_ms",
    "continuity",
    "output_validation",
    "artifacts",
}
TIMING_FIELDS = {
    "backend_first_packet_ms",
    "postfx_first_packet_ms",
    "routing_first_packet_ms",
    "e2e_first_packet_ms",
    "e2e_p50_ms",
    "e2e_p95_ms",
}
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _blocked(message: str) -> tuple[str, list[str]]:
    return "BLOCKED", [message]


def classify(record: dict[str, Any]) -> tuple[str, list[str]]:
    """回傳 PASS、OFFLINE、WAITING 或 BLOCKED，並保留可讀原因。"""

    missing = sorted(REQUIRED - record.keys())
    if missing:
        return _blocked(f"missing top-level fields: {', '.join(missing)}")
    if record.get("schema_version") != "aethertune-audio-rack/evidence-v1":
        return _blocked("schema_version must be aethertune-audio-rack/evidence-v1")
    if record.get("rack_mode") not in {"bypass", "full-chain"}:
        return _blocked("rack_mode must be bypass or full-chain")

    timing = record["timing_ms"]
    if not isinstance(timing, dict):
        return _blocked("timing_ms must be an object")
    missing_timing = sorted(TIMING_FIELDS - timing.keys())
    if missing_timing:
        return _blocked(f"missing timing fields: {', '.join(missing_timing)}")
    bad_timing = [field for field in TIMING_FIELDS if not _number(timing[field]) or timing[field] < 0]
    if bad_timing:
        return _blocked(f"timing fields must be finite non-negative numbers: {', '.join(sorted(bad_timing))}")

    continuity = record["continuity"]
    if not isinstance(continuity, dict):
        return _blocked("continuity must be an object")
    for field in ("continuous_seconds", "dropouts", "underruns"):
        if field not in continuity:
            return _blocked(f"missing continuity field: {field}")
    if not _number(continuity["continuous_seconds"]) or continuity["continuous_seconds"] < 0:
        return _blocked("continuous_seconds must be finite and non-negative")
    if any(not isinstance(continuity[field], int) or continuity[field] < 0 for field in ("dropouts", "underruns")):
        return _blocked("dropouts and underruns must be non-negative integers")

    output = record["output_validation"]
    if not isinstance(output, dict):
        return _blocked("output_validation must be an object")
    if output.get("status") == "WAITING":
        return "WAITING", ["output_validation is still WAITING"]
    if output.get("status") != "PASS" or output.get("finite") is not True or output.get("non_zero") is not True:
        return _blocked("output_validation must be PASS with finite=true and non_zero=true")

    artifacts = record["artifacts"]
    if not isinstance(artifacts, dict):
        return _blocked("artifacts must be an object")
    for field in ("output_wav", "metrics_json"):
        if not isinstance(artifacts.get(field), str) or not artifacts[field].strip():
            return _blocked(f"artifacts.{field} must be a non-empty path")
    if not isinstance(artifacts.get("wav_sha256"), str) or not SHA256_RE.fullmatch(artifacts["wav_sha256"]):
        return _blocked("artifacts.wav_sha256 must be a 64-character SHA-256")

    if record.get("delta_latency_ms") is None:
        return "WAITING", ["delta_latency_ms is missing; paired bypass/full-chain latency is not proven"]
    if not _number(record["delta_latency_ms"]) or record["delta_latency_ms"] < 0:
        return _blocked("delta_latency_ms must be null or a finite non-negative number")

    if timing["e2e_first_packet_ms"] > 5000:
        return "OFFLINE", [f"e2e_first_packet_ms={timing['e2e_first_packet_ms']:g} exceeds the 5000 ms LIVE budget"]

    warnings: list[str] = []
    if continuity["continuous_seconds"] < 60:
        warnings.append("continuous_seconds is below the 60 s screening target")
    if continuity["dropouts"] or continuity["underruns"]:
        warnings.append("dropouts or underruns are present")
    return "PASS", warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify AetherTune audio-rack evidence")
    parser.add_argument("evidence", type=Path, help="path to an audio-rack/evidence-v1 JSON file")
    args = parser.parse_args()

    try:
        record = json.loads(args.evidence.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"BLOCKED: evidence file not found: {args.evidence}")
        return 2
    except (OSError, json.JSONDecodeError) as error:
        print(f"BLOCKED: cannot read evidence: {error}")
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
