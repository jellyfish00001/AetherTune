"""Classify local LIVE_GATE evidence; file and identity checks never create evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from audio_output_validation import validate_wav_file


REQUIRED_TOP_LEVEL = {
    "schema_version",
    "run_id",
    "run_started_at_utc",
    "backend_id",
    "route_profile",
    "model",
    "hardware",
    "capture",
    "route",
    "timing_ms",
    "continuity",
    "output_validation",
    "artifacts",
    "human_review",
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
REQUIRED_HUMAN_RATINGS = {
    "naturalness",
    "target_similarity",
    "performance_preservation",
    "content_accuracy",
    "noise_artifacts",
    "acceptability",
}
WAV_METADATA_FIELDS = {"sample_rate_hz", "channels", "frames", "duration_sec"}
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
PLACEHOLDERS = {"", "unknown", "fixture", "placeholder", "n/a", "none", "test"}


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _strict_json_equal(actual: Any, expected: Any) -> bool:
    """Compare JSON-shaped values without Python's bool-as-int equality coercion."""

    if isinstance(actual, bool) or isinstance(expected, bool):
        return isinstance(actual, bool) and isinstance(expected, bool) and actual is expected
    if isinstance(actual, dict) or isinstance(expected, dict):
        return (
            isinstance(actual, dict)
            and isinstance(expected, dict)
            and actual.keys() == expected.keys()
            and all(_strict_json_equal(actual[key], expected[key]) for key in expected)
        )
    if isinstance(actual, list) or isinstance(expected, list):
        return (
            isinstance(actual, list)
            and isinstance(expected, list)
            and len(actual) == len(expected)
            and all(_strict_json_equal(left, right) for left, right in zip(actual, expected))
        )
    if isinstance(actual, (int, float)) or isinstance(expected, (int, float)):
        return (
            isinstance(actual, (int, float))
            and not isinstance(actual, bool)
            and isinstance(expected, (int, float))
            and not isinstance(expected, bool)
            and actual == expected
        )
    return type(actual) is type(expected) and actual == expected


def _fail(message: str) -> tuple[str, list[str]]:
    return "BLOCKED", [message]


def _wait(message: str) -> tuple[str, list[str]]:
    return "WAITING", [message]


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _non_placeholder(value: Any) -> bool:
    return isinstance(value, str) and value.strip().casefold() not in PLACEHOLDERS


def _artifact_path(root: Path, value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"artifacts.{label} must be a non-empty path")
    candidate = Path(value)
    return candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()


def _wav_metadata(audio: dict[str, Any]) -> dict[str, Any]:
    """Return stable header facts used by the evidence and its hash-bound metrics."""

    return {
        "sample_rate_hz": audio["sample_rate"],
        "channels": audio["channels"],
        "frames": audio["frames"],
        "duration_sec": audio["duration_sec"],
    }


def _metadata_matches(declared: Any, actual: dict[str, Any]) -> bool:
    if not isinstance(declared, dict) or not WAV_METADATA_FIELDS.issubset(declared):
        return False
    for key in ("sample_rate_hz", "channels", "frames"):
        value = declared.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value != actual[key]:
            return False
    duration = declared.get("duration_sec")
    return _is_number(duration) and math.isclose(float(duration), actual["duration_sec"], rel_tol=0, abs_tol=1e-9)


def _verify_file(root: Path, value: Any, expected_hash: Any, label: str, started: datetime) -> Path:
    if not isinstance(expected_hash, str) or not SHA256_RE.fullmatch(expected_hash):
        raise ValueError(f"artifacts.{label}_sha256 must be a 64-character SHA-256")
    path = _artifact_path(root, value, label)
    if not path.is_file() or path.stat().st_size <= 0:
        raise ValueError(f"artifacts.{label} is missing or empty: {path}")
    actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual_hash.casefold() != expected_hash.casefold():
        raise ValueError(f"artifacts.{label} SHA-256 mismatch")
    # NTFS timestamps and clocks can differ slightly; two seconds accommodates resolution/skew,
    # while still rejecting an old WAV that merely remains in an output directory.
    modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    if modified.timestamp() < started.timestamp() - 2.0:
        raise ValueError(f"artifacts.{label} predates this run and is stale")
    return path


def classify(record: dict[str, Any], artifact_root: Path | None = None) -> tuple[str, list[str]]:
    """Return LIVE, LIVE_CANDIDATE, OFFLINE, WAITING, or BLOCKED from local evidence."""

    missing = sorted(REQUIRED_TOP_LEVEL - record.keys())
    if missing:
        return _wait(f"missing evidence fields: {', '.join(missing)}")
    if record.get("schema_version") != "aethertune-live-gate/v1":
        return _fail("schema_version must be aethertune-live-gate/v1")
    if not _non_placeholder(record.get("run_id")):
        return _fail("run_id must identify a concrete run")

    started = _parse_time(record.get("run_started_at_utc"))
    if started is None:
        return _fail("run_started_at_utc must be an ISO-8601 timestamp with timezone")

    capture = record.get("capture")
    if not isinstance(capture, dict):
        return _fail("capture must be an object")
    if capture.get("source_type") != "physical_microphone":
        return _wait("capture source is not verified as a physical microphone; synthetic/file input cannot pass LIVE")

    for field in ("backend_id", "route_profile"):
        if not _non_placeholder(record.get(field)):
            return _fail(f"{field} must identify a concrete backend/route")

    model = record.get("model")
    if not isinstance(model, dict):
        return _wait("model identity is missing")
    if not all(_non_placeholder(model.get(key)) for key in ("model_id", "revision")):
        return _wait("model_id and pinned revision are required")
    if not isinstance(model.get("checkpoint_sha256"), str) or not SHA256_RE.fullmatch(model["checkpoint_sha256"]):
        return _fail("model.checkpoint_sha256 must be a 64-character SHA-256")

    hardware = record.get("hardware")
    if not isinstance(hardware, dict) or not all(
        _non_placeholder(hardware.get(key)) for key in ("gpu", "gpu_id", "driver_version", "audio_interface", "audio_driver")
    ):
        return _wait("GPU, driver, and audio hardware identity are incomplete")
    if not all(_non_placeholder(capture.get(key)) for key in ("device_name", "device_id")):
        return _wait("physical microphone name and device identity are required")
    if not isinstance(capture.get("sample_rate_hz"), int) or isinstance(capture["sample_rate_hz"], bool) or capture["sample_rate_hz"] <= 0:
        return _fail("capture.sample_rate_hz must be a positive integer")
    if not isinstance(capture.get("channels"), int) or isinstance(capture["channels"], bool) or capture["channels"] <= 0:
        return _fail("capture.channels must be a positive integer")

    route = record.get("route")
    if not isinstance(route, dict) or not all(
        _non_placeholder(route.get(key)) for key in ("route_id", "input_endpoint", "output_endpoint", "audio_driver")
    ):
        return _wait("route identity must name the capture input and final output endpoints")

    timing = record.get("timing_ms")
    if not isinstance(timing, dict):
        return _fail("timing_ms must be an object")
    missing_timing = sorted(REQUIRED_TIMINGS - timing.keys())
    if missing_timing:
        return _wait(f"missing timing fields: {', '.join(missing_timing)}")
    bad_timing = [key for key in REQUIRED_TIMINGS if not _is_number(timing[key]) or timing[key] < 0]
    if bad_timing:
        return _fail(f"timing fields must be finite non-negative numbers: {', '.join(sorted(bad_timing))}")

    continuity = record.get("continuity")
    if not isinstance(continuity, dict):
        return _fail("continuity must be an object")
    for key in ("continuous_seconds", "dropouts", "underruns"):
        if key not in continuity:
            return _wait(f"missing continuity field: {key}")
    if not _is_number(continuity["continuous_seconds"]) or continuity["continuous_seconds"] < 0:
        return _fail("continuous_seconds must be a finite non-negative number")
    if any(
        not isinstance(continuity[key], int) or isinstance(continuity[key], bool) or continuity[key] < 0
        for key in ("dropouts", "underruns")
    ):
        return _fail("dropouts and underruns must be non-negative integers")

    output = record.get("output_validation")
    if not isinstance(output, dict):
        return _fail("output_validation must be an object")
    if output.get("status") == "WAITING":
        return _wait("output_validation is still WAITING")
    if output.get("status") != "PASS" or output.get("finite") is not True or output.get("non_zero") is not True:
        return _fail("output_validation must be PASS with finite=true and non_zero=true")

    artifacts = record.get("artifacts")
    if not isinstance(artifacts, dict):
        return _wait("artifact paths and hashes are required")
    root = (artifact_root or Path.cwd()).resolve()
    try:
        input_wav = _verify_file(root, artifacts.get("input_wav"), artifacts.get("input_sha256"), "input_wav", started)
        output_wav = _verify_file(root, artifacts.get("output_wav"), artifacts.get("output_sha256"), "output_wav", started)
        input_audio = validate_wav_file(input_wav)
        output_audio = validate_wav_file(output_wav)
        input_metadata = _wav_metadata(input_audio)
        output_metadata = _wav_metadata(output_audio)
        if capture["sample_rate_hz"] != input_metadata["sample_rate_hz"] or capture["channels"] != input_metadata["channels"]:
            return _fail("capture sample_rate_hz/channels do not match the input WAV header")
        if not _metadata_matches(output, output_metadata):
            return _fail("output_validation WAV metadata does not match the output WAV header")
        if output_audio["peak"] <= 1e-5:
            return _fail("output WAV is effectively silent")
        metrics_path = _artifact_path(root, artifacts.get("metrics_json"), "metrics_json")
        metrics_hash = artifacts.get("metrics_sha256")
        if not isinstance(metrics_hash, str) or not SHA256_RE.fullmatch(metrics_hash):
            return _fail("artifacts.metrics_sha256 must be a 64-character SHA-256")
        if not metrics_path.is_file() or hashlib.sha256(metrics_path.read_bytes()).hexdigest().casefold() != metrics_hash.casefold():
            return _fail("metrics JSON is missing or its SHA-256 does not match")
        if metrics_path.stat().st_mtime < started.timestamp() - 2.0:
            return _fail("metrics JSON predates this run and is stale")
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        if not isinstance(metrics, dict):
            return _fail("metrics JSON root must be an object")
        expected_metrics = {
            "run_id": record["run_id"],
            "backend_id": record["backend_id"],
            "route_profile": record["route_profile"],
            "model_id": model["model_id"],
            "model_revision": model["revision"],
            "model_checkpoint_sha256": model["checkpoint_sha256"],
            "source_sha256": artifacts["input_sha256"],
            "output_sha256": artifacts["output_sha256"],
            "route_id": route["route_id"],
            "gpu_id": hardware["gpu_id"],
            "driver_version": hardware["driver_version"],
            "audio_interface": hardware["audio_interface"],
            "audio_driver": hardware["audio_driver"],
            "capture_device_id": capture["device_id"],
            "capture_source_type": capture["source_type"],
            "capture_sample_rate_hz": capture["sample_rate_hz"],
            "capture_channels": capture["channels"],
            "input_wav_metadata": input_metadata,
            "output_wav_metadata": output_metadata,
            "input_endpoint": route["input_endpoint"],
            "output_endpoint": route["output_endpoint"],
            # Metrics are a hash-bound copy of the full run measurements and review record.
            # Binding only first-packet latency left continuity and human scores editable.
            "timing_ms": timing,
            "continuity": continuity,
            "human_review": record["human_review"],
        }
        for key, expected in expected_metrics.items():
            if not _strict_json_equal(metrics.get(key), expected):
                return _fail(f"metrics JSON identity mismatch for {key}")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return _fail(str(error))

    first_packet = timing["e2e_first_packet_ms"]
    if first_packet > 5000:
        return "OFFLINE", [f"e2e_first_packet_ms={first_packet:g} exceeds the 5000 ms LIVE budget"]

    candidate_reasons: list[str] = []
    if continuity["continuous_seconds"] < 600:
        candidate_reasons.append("600 s stability evidence is required for LIVE")
    if continuity["dropouts"] or continuity["underruns"]:
        candidate_reasons.append("dropouts or underruns must be zero for LIVE")
    if continuity["continuous_seconds"] < 60:
        candidate_reasons.append("continuous_seconds is below the 60 s screening target")
    human = record["human_review"]
    if not isinstance(human, dict):
        return _fail("human_review must be an object")
    if human.get("status") == "WAITING":
        candidate_reasons.append("human listening review is still WAITING")
    elif human.get("status") != "PASS":
        return _fail("human_review.status must be PASS or WAITING")
    else:
        review_errors: list[str] = []
        if not _non_placeholder(human.get("review_id")) or not _non_placeholder(human.get("reviewer_id")):
            review_errors.append("concrete reviewer_id and review_id")
        reviewed_at = _parse_time(human.get("reviewed_at_utc"))
        if reviewed_at is None:
            review_errors.append("timezone-aware reviewed_at_utc")
        if human.get("input_sha256") != artifacts.get("input_sha256") or human.get("output_sha256") != artifacts.get("output_sha256"):
            review_errors.append("the exact input/output WAV hashes")
        ratings = human.get("ratings")
        if not isinstance(ratings, dict) or REQUIRED_HUMAN_RATINGS - ratings.keys():
            review_errors.append("all required listening ratings")
        elif any(
            not _is_number(ratings[key]) or not 1 <= ratings[key] <= 5
            for key in REQUIRED_HUMAN_RATINGS
        ):
            review_errors.append("finite listening ratings from 1 to 5")
        if review_errors:
            return _fail("human_review.status=PASS is incomplete: " + ", ".join(review_errors))
    if candidate_reasons:
        return "LIVE_CANDIDATE", candidate_reasons
    return "LIVE", [f"verified input duration={input_audio['duration_sec']:.3f}s; output duration={output_audio['duration_sec']:.3f}s"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify evidence-only AetherTune LIVE_GATE records")
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
    status, messages = classify(record, args.evidence.parent)
    for message in messages:
        print(f"{status}: {message}")
    print(f"classification={status}")
    if status == "BLOCKED":
        return 2
    if status in {"WAITING", "LIVE_CANDIDATE"}:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
