"""Validate audio-rack evidence against real files, hashes, and paired rack runs."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
import sys
from pathlib import Path
from typing import Any


HELPERS = Path(__file__).resolve().parent
sys.path.insert(0, str(HELPERS))
WAV_SPEC = importlib.util.spec_from_file_location("wav_evidence", HELPERS / "wav-evidence.py")
assert WAV_SPEC and WAV_SPEC.loader
WAV_MODULE = importlib.util.module_from_spec(WAV_SPEC)
WAV_SPEC.loader.exec_module(WAV_MODULE)
validate_wav = WAV_MODULE.validate_wav
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")

REQUIRED = {
    "schema_version",
    "run_id",
    "pair_group_id",
    "backend_id",
    "route_profile",
    "rack_mode",
    "capture",
    "timing_ms",
    "continuity",
    "output_validation",
    "artifacts",
    "delta_latency_ms",
}
TIMING_FIELDS = {
    "backend_first_packet_ms",
    "postfx_first_packet_ms",
    "routing_first_packet_ms",
    "e2e_first_packet_ms",
    "e2e_p50_ms",
    "e2e_p95_ms",
}


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _blocked(message: str) -> tuple[str, list[str]]:
    return "BLOCKED", [message]


def _resolve_path(value: Any, root: Path) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _check_wav(path_value: Any, hash_value: Any, label: str, root: Path) -> tuple[str, dict[str, Any] | None, str | None]:
    path = _resolve_path(path_value, root)
    if path is None:
        return "BLOCKED", None, f"{label} path must be a non-empty path"
    if not isinstance(hash_value, str) or not SHA256_RE.fullmatch(hash_value):
        return "BLOCKED", None, f"{label} SHA-256 must be a 64-character hex digest"
    try:
        report = validate_wav(path)
    except (OSError, ValueError) as exc:
        return "BLOCKED", None, f"{label} WAV validation failed: {exc}"
    if report["sha256"].lower() != hash_value.lower():
        return "BLOCKED", report, f"{label} SHA-256 does not match the referenced WAV"
    if report["non_zero"] is not True:
        return "BLOCKED", report, f"{label} WAV is silent"
    return "PASS", report, None


def _validate_core(record: dict[str, Any], root: Path) -> tuple[str, list[str], dict[str, Any] | None]:
    missing = sorted(REQUIRED - record.keys())
    if missing:
        return "BLOCKED", [f"missing top-level fields: {', '.join(missing)}"], None
    if record.get("schema_version") != "aethertune-audio-rack/evidence-v1":
        return "BLOCKED", ["schema_version must be aethertune-audio-rack/evidence-v1"], None
    for key in ("run_id", "pair_group_id", "backend_id", "route_profile"):
        if not isinstance(record.get(key), str) or not record[key].strip():
            return "BLOCKED", [f"{key} must be a non-empty string"], None
    if record.get("rack_mode") not in {"bypass", "full-chain"}:
        return "BLOCKED", ["rack_mode must be bypass or full-chain"], None

    capture = record["capture"]
    if not isinstance(capture, dict):
        return "BLOCKED", ["capture must be an object"], None
    for key in ("input_wav", "input_sha256", "reference_wav", "reference_sha256"):
        if key not in capture:
            return "BLOCKED", [f"missing capture field: {key}"], None
    for path_key, hash_key, label in (
        ("input_wav", "input_sha256", "captured source"),
        ("reference_wav", "reference_sha256", "reference"),
    ):
        status, _, message = _check_wav(capture[path_key], capture[hash_key], label, root)
        if status != "PASS":
            return "BLOCKED", [message or f"{label} WAV validation failed"], None

    timing = record["timing_ms"]
    if not isinstance(timing, dict):
        return "BLOCKED", ["timing_ms must be an object"], None
    missing_timing = sorted(TIMING_FIELDS - timing.keys())
    if missing_timing:
        return "BLOCKED", [f"missing timing fields: {', '.join(missing_timing)}"], None
    bad_timing = [field for field in TIMING_FIELDS if not _number(timing[field]) or timing[field] < 0]
    if bad_timing:
        return "BLOCKED", [f"timing fields must be finite non-negative numbers: {', '.join(sorted(bad_timing))}"], None

    continuity = record["continuity"]
    if not isinstance(continuity, dict):
        return "BLOCKED", ["continuity must be an object"], None
    for field in ("continuous_seconds", "dropouts", "underruns"):
        if field not in continuity:
            return "BLOCKED", [f"missing continuity field: {field}"], None
    if not _number(continuity["continuous_seconds"]) or continuity["continuous_seconds"] < 0:
        return "BLOCKED", ["continuous_seconds must be finite and non-negative"], None
    if any(not isinstance(continuity[field], int) or isinstance(continuity[field], bool) or continuity[field] < 0 for field in ("dropouts", "underruns")):
        return "BLOCKED", ["dropouts and underruns must be non-negative integers"], None

    output = record["output_validation"]
    if not isinstance(output, dict):
        return "BLOCKED", ["output_validation must be an object"], None
    if output.get("status") == "WAITING":
        return "WAITING", ["output_validation is still WAITING for a routed WAV"], None
    if output.get("status") != "PASS" or output.get("finite") is not True or output.get("non_zero") is not True:
        return "BLOCKED", ["output_validation must be PASS with finite=true and non_zero=true"], None

    artifacts = record["artifacts"]
    if not isinstance(artifacts, dict):
        return "BLOCKED", ["artifacts must be an object"], None
    for field in ("output_wav", "metrics_json", "wav_sha256"):
        if field not in artifacts:
            return "BLOCKED", [f"missing artifacts field: {field}"], None
    wav_status, wav_report, message = _check_wav(
        artifacts["output_wav"], artifacts["wav_sha256"], "routed output", root
    )
    if wav_status != "PASS" or wav_report is None:
        return "BLOCKED", [message or "routed output validation failed"], None

    metrics_path = _resolve_path(artifacts["metrics_json"], root)
    if metrics_path is None or not metrics_path.is_file():
        return "BLOCKED", ["artifacts.metrics_json must reference an existing JSON file"], None
    try:
        metrics = json.loads(metrics_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return "BLOCKED", [f"cannot read metrics_json: {exc}"], None
    if not isinstance(metrics, dict):
        return "BLOCKED", ["metrics_json root must be an object"], None
    identity = {
        "run_id": record["run_id"],
        "wav_sha256": artifacts["wav_sha256"],
        "input_sha256": capture["input_sha256"],
        "reference_sha256": capture["reference_sha256"],
    }
    for key, expected in identity.items():
        actual = metrics.get(key)
        if not isinstance(actual, str) or actual.casefold() != expected.casefold():
            return "BLOCKED", [f"metrics_json {key} does not match this evidence record"], None

    delta = record["delta_latency_ms"]
    if delta is not None and not _number(delta):
        return "BLOCKED", ["delta_latency_ms must be null or a finite number"], None
    if not isinstance(artifacts.get("paired_evidence_path"), str) or not artifacts["paired_evidence_path"].strip():
        return "WAITING", ["paired_evidence_path is missing; bypass/full-chain A/B cannot be verified"], None
    return "PASS", [], {"timing": timing, "capture": capture, "wav": wav_report, "metrics": metrics}


def classify(record: dict[str, Any], artifact_root: Path | None = None, _validate_pair: bool = True) -> tuple[str, list[str]]:
    """Return PASS, OFFLINE, WAITING, or BLOCKED after checking files and a paired run."""

    root = (artifact_root or PROJECT_ROOT).resolve()
    status, messages, core = _validate_core(record, root)
    if status != "PASS" or core is None:
        return status, messages

    pair_path = _resolve_path(record["artifacts"].get("paired_evidence_path"), root)
    if pair_path is None or not pair_path.is_file():
        return "WAITING", [f"paired evidence JSON is not available: {pair_path or '(missing)'}"]
    if not _validate_pair:
        return "PASS", []
    try:
        paired = json.loads(pair_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return _blocked(f"cannot read paired evidence JSON: {exc}")
    if not isinstance(paired, dict):
        return _blocked("paired evidence root must be an object")
    paired_status, paired_messages, paired_core = _validate_core(paired, root)
    if paired_status == "WAITING":
        return "WAITING", ["paired evidence is still WAITING"] + paired_messages
    if paired_status != "PASS" or paired_core is None:
        return _blocked("paired evidence is invalid: " + "; ".join(paired_messages))
    if paired["rack_mode"] == record["rack_mode"]:
        return _blocked("paired evidence must use the opposite rack_mode")
    for key in ("pair_group_id", "backend_id", "route_profile"):
        if paired.get(key) != record.get(key):
            return _blocked(f"paired evidence {key} does not match")
    if paired.get("run_id") == record.get("run_id"):
        return _blocked("paired evidence must have a distinct run_id")
    for key in ("input_sha256", "reference_sha256"):
        left = record["capture"].get(key)
        right = paired["capture"].get(key)
        if not isinstance(left, str) or not isinstance(right, str) or left.casefold() != right.casefold():
            return _blocked(f"paired evidence capture.{key} does not match")

    reported_delta = record["delta_latency_ms"]
    if reported_delta is None:
        return "WAITING", ["delta_latency_ms is null; measured paired-run latency delta is required"]
    expected_delta = record["timing_ms"]["e2e_first_packet_ms"] - paired["timing_ms"]["e2e_first_packet_ms"]
    if not math.isclose(reported_delta, expected_delta, rel_tol=0.0, abs_tol=0.5):
        return _blocked(
            f"delta_latency_ms={reported_delta:g} does not match this run minus paired run ({expected_delta:g} ms)"
        )

    paired_delta = paired.get("delta_latency_ms")
    if paired_delta is None:
        return "WAITING", ["paired evidence delta_latency_ms is null"]
    expected_paired_delta = paired["timing_ms"]["e2e_first_packet_ms"] - record["timing_ms"]["e2e_first_packet_ms"]
    if not _number(paired_delta) or not math.isclose(
        paired_delta, expected_paired_delta, rel_tol=0.0, abs_tol=0.5
    ):
        return _blocked("paired evidence delta_latency_ms does not equal its run minus this run")

    paired_back_path = _resolve_path(paired["artifacts"].get("paired_evidence_path"), root)
    if paired_back_path is None or not paired_back_path.is_file():
        return "WAITING", ["paired evidence does not point back to an available counterpart"]
    try:
        paired_back = json.loads(paired_back_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return _blocked(f"cannot read paired counterpart evidence JSON: {exc}")
    if not isinstance(paired_back, dict):
        return _blocked("paired counterpart evidence root must be an object")
    back_status, back_messages, _ = _validate_core(paired_back, root)
    if back_status == "WAITING":
        return "WAITING", ["paired counterpart is still WAITING"] + back_messages
    if back_status != "PASS":
        return _blocked("paired counterpart is invalid: " + "; ".join(back_messages))
    for key in ("run_id", "pair_group_id", "backend_id", "route_profile", "rack_mode"):
        if paired_back.get(key) != record.get(key):
            return _blocked(f"paired counterpart {key} does not match this record")
    for key in ("input_sha256", "reference_sha256"):
        if paired_back["capture"].get(key, "").casefold() != record["capture"].get(key, "").casefold():
            return _blocked(f"paired counterpart capture.{key} does not match this record")
    if paired_back["artifacts"].get("wav_sha256", "").casefold() != record["artifacts"].get("wav_sha256", "").casefold():
        return _blocked("paired counterpart output WAV identity does not match this record")
    for key in TIMING_FIELDS:
        if not math.isclose(
            paired_back["timing_ms"][key], record["timing_ms"][key], rel_tol=0.0, abs_tol=0.5
        ):
            return _blocked(f"paired counterpart timing_ms.{key} does not match this record")
    back_delta = paired_back.get("delta_latency_ms")
    if not _number(back_delta) or not math.isclose(back_delta, reported_delta, rel_tol=0.0, abs_tol=0.5):
        return _blocked("paired counterpart delta_latency_ms does not match this record")

    if record["timing_ms"]["e2e_first_packet_ms"] > 5000:
        return "OFFLINE", [f"e2e_first_packet_ms={record['timing_ms']['e2e_first_packet_ms']:g} exceeds the 5000 ms LIVE budget"]
    continuity = record["continuity"]
    warnings: list[str] = []
    if continuity["continuous_seconds"] < 60:
        warnings.append("continuous_seconds is below the 60 s screening target")
    if continuity["dropouts"] or continuity["underruns"]:
        warnings.append("dropouts or underruns are present")
    return "PASS", warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AetherTune paired audio-rack evidence")
    parser.add_argument("evidence", type=Path, help="path to an audio-rack/evidence-v1 JSON file")
    args = parser.parse_args()
    try:
        record = json.loads(args.evidence.read_text(encoding="utf-8-sig"))
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
    return {"PASS": 0, "OFFLINE": 0, "WAITING": 3, "BLOCKED": 2}.get(status, 2)


if __name__ == "__main__":
    sys.exit(main())
