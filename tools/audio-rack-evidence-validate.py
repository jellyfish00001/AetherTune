"""Validate paired A/B audio-rack evidence without creating or upgrading evidence."""

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


REQUIRED = {
    "schema_version",
    "pair_id",
    "backend_id",
    "route_profile",
    "source",
    "model",
    "hardware",
    "route",
    "runs",
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
SOURCE_TYPES = {"physical_microphone", "synthetic_callback", "file_injection"}
WAV_METADATA_FIELDS = {"sample_rate_hz", "channels", "frames", "duration_sec"}
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
PLACEHOLDERS = {"", "unknown", "fixture", "placeholder", "n/a", "none", "test"}


def _number(value: Any) -> bool:
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


def _non_placeholder(value: Any) -> bool:
    return isinstance(value, str) and value.strip().casefold() not in PLACEHOLDERS


def _blocked(message: str) -> tuple[str, list[str]]:
    return "BLOCKED", [message]


def _resolve_artifact(root: Path, value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty artifact path")
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _wav_metadata(audio: dict[str, Any]) -> dict[str, Any]:
    return {
        "sample_rate_hz": audio["sample_rate"],
        "channels": audio["channels"],
        "frames": audio["frames"],
        "duration_sec": audio["duration_sec"],
    }


def _metadata_matches(declared: Any, actual: dict[str, Any]) -> bool:
    if not isinstance(declared, dict) or set(declared) != WAV_METADATA_FIELDS:
        return False
    for key in ("sample_rate_hz", "channels", "frames"):
        value = declared.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value != actual[key]:
            return False
    duration = declared.get("duration_sec")
    return _number(duration) and math.isclose(float(duration), actual["duration_sec"], rel_tol=0, abs_tol=1e-9)


def _verify_audio(root: Path, value: Any, expected_hash: Any, label: str, started: datetime | None) -> tuple[Path, dict[str, Any]]:
    if not isinstance(expected_hash, str) or not SHA256_RE.fullmatch(expected_hash):
        raise ValueError(f"{label}_sha256 must be a 64-character SHA-256")
    path = _resolve_artifact(root, value, label)
    if not path.is_file() or path.stat().st_size <= 0:
        raise ValueError(f"{label} is missing or empty: {path}")
    actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual_hash.casefold() != expected_hash.casefold():
        raise ValueError(f"{label} SHA-256 mismatch")
    if started is not None:
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        if modified.timestamp() < started.timestamp() - 2.0:
            raise ValueError(f"{label} predates this run and is stale")
    return path, validate_wav_file(path)


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


def classify(record: dict[str, Any], artifact_root: Path | None = None) -> tuple[str, list[str]]:
    """回傳 PASS、OFFLINE、WAITING 或 BLOCKED；PASS 僅指 rack A/B evidence。"""

    if not isinstance(record, dict):
        return _blocked("evidence root must be an object")
    missing = sorted(REQUIRED - record.keys())
    if missing:
        return _blocked(f"missing top-level fields: {', '.join(missing)}")
    if record.get("schema_version") != "aethertune-audio-rack/evidence-v1":
        return _blocked("schema_version must be aethertune-audio-rack/evidence-v1")
    for field in ("pair_id", "backend_id", "route_profile"):
        if not _non_placeholder(record.get(field)):
            return _blocked(f"{field} must identify a concrete value")

    source = record.get("source")
    if not isinstance(source, dict):
        return _blocked("source must be an object with a WAV path and SHA-256")
    if source.get("source_type") not in SOURCE_TYPES:
        return _blocked("source.source_type must be physical_microphone, synthetic_callback, or file_injection")
    for field in ("sample_rate_hz", "channels"):
        value = source.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            return _blocked(f"source.{field} must be a positive integer")
    model = record.get("model")
    hardware = record.get("hardware")
    route = record.get("route")
    if not isinstance(model, dict) or not all(_non_placeholder(model.get(key)) for key in ("model_id", "revision")):
        return _blocked("model identity requires model_id and pinned revision")
    if not isinstance(model.get("checkpoint_sha256"), str) or not SHA256_RE.fullmatch(model["checkpoint_sha256"]):
        return _blocked("model.checkpoint_sha256 must be a 64-character SHA-256")
    if not isinstance(hardware, dict) or not all(
        _non_placeholder(hardware.get(key)) for key in ("gpu", "gpu_id", "driver_version", "audio_interface", "audio_driver")
    ):
        return _blocked("hardware identity is incomplete")
    if not isinstance(route, dict) or not all(
        _non_placeholder(route.get(key)) for key in ("route_id", "input_endpoint", "output_endpoint", "audio_driver")
    ):
        return _blocked("route identity is incomplete")

    try:
        root = (artifact_root or Path.cwd()).resolve()
        source_path, source_audio = _verify_audio(root, source.get("wav"), source.get("sha256"), "source.wav", None)
        source_metadata = _wav_metadata(source_audio)
        if source["sample_rate_hz"] != source_metadata["sample_rate_hz"] or source["channels"] != source_metadata["channels"]:
            return _blocked("source sample_rate_hz/channels do not match the source WAV header")
    except (OSError, ValueError) as error:
        return _blocked(str(error))

    runs = record.get("runs")
    if not isinstance(runs, dict) or set(runs) != {"bypass", "full_chain"}:
        return "WAITING", ["paired bypass and full_chain runs are required"]
    if not isinstance(record.get("delta_latency_ms"), (int, float)) or isinstance(record["delta_latency_ms"], bool) or not _number(record["delta_latency_ms"]):
        return "WAITING", ["measured delta_latency_ms is required for a paired rack comparison"]

    run_ids: set[str] = set()
    latencies: dict[str, float] = {}
    verified: list[dict[str, Any]] = []
    for mode in ("bypass", "full_chain"):
        run = runs[mode]
        if not isinstance(run, dict):
            return _blocked(f"runs.{mode} must be an object")
        run_id = run.get("run_id")
        if not _non_placeholder(run_id) or run_id in run_ids:
            return _blocked("bypass and full_chain require distinct concrete run_id values")
        run_ids.add(run_id)
        paired_mode = "full_chain" if mode == "bypass" else "bypass"
        paired_run = runs.get(paired_mode)
        if not isinstance(paired_run, dict):
            return _blocked(f"runs.{paired_mode} must be an object to bind the paired metrics identity")
        paired_artifacts = paired_run.get("artifacts")
        paired_timing = paired_run.get("timing_ms")
        if not isinstance(paired_artifacts, dict) or not isinstance(paired_timing, dict):
            return _blocked(f"runs.{paired_mode} needs artifacts and timing_ms for pair binding")
        if run.get("rack_mode") != mode:
            return _blocked(f"runs.{mode}.rack_mode must be {mode}")
        started = _parse_time(run.get("started_at_utc"))
        if started is None:
            return _blocked(f"runs.{mode}.started_at_utc must be timezone-aware ISO-8601")

        timing = run.get("timing_ms")
        if not isinstance(timing, dict) or sorted(TIMING_FIELDS - timing.keys()):
            return _blocked(f"runs.{mode}.timing_ms is incomplete")
        if any(not _number(timing[field]) or timing[field] < 0 for field in TIMING_FIELDS):
            return _blocked(f"runs.{mode}.timing_ms contains invalid values")
        latencies[mode] = float(timing["e2e_first_packet_ms"])

        continuity = run.get("continuity")
        if not isinstance(continuity, dict):
            return _blocked(f"runs.{mode}.continuity must be an object")
        if not _number(continuity.get("continuous_seconds")) or continuity["continuous_seconds"] < 0:
            return _blocked(f"runs.{mode}.continuous_seconds must be finite and non-negative")
        if any(
            not isinstance(continuity.get(key), int)
            or isinstance(continuity.get(key), bool)
            or continuity[key] < 0
            for key in ("dropouts", "underruns")
        ):
            return _blocked(f"runs.{mode}.dropouts and underruns must be non-negative integers")

        output = run.get("output_validation")
        if not isinstance(output, dict):
            return _blocked(f"runs.{mode}.output_validation must be an object")
        if output.get("status") == "WAITING":
            return "WAITING", [f"runs.{mode}.output_validation is still WAITING"]
        if output.get("status") != "PASS" or output.get("finite") is not True or output.get("non_zero") is not True:
            return _blocked(f"runs.{mode}.output_validation must be PASS with finite=true and non_zero=true")

        artifacts = run.get("artifacts")
        if not isinstance(artifacts, dict):
            return _blocked(f"runs.{mode}.artifacts must be an object")
        try:
            output_path, audio_metrics = _verify_audio(
                root, artifacts.get("output_wav"), artifacts.get("wav_sha256"), f"runs.{mode}.output_wav", started
            )
            output_metadata = _wav_metadata(audio_metrics)
            if not _metadata_matches(run.get("output_metadata"), output_metadata):
                return _blocked(f"runs.{mode}.output_metadata does not match the output WAV header")
            if audio_metrics["peak"] <= 1e-5:
                return _blocked(f"runs.{mode}.output_wav is effectively silent")
            metrics_path = _resolve_artifact(root, artifacts.get("metrics_json"), f"runs.{mode}.metrics_json")
            metrics_sha = artifacts.get("metrics_sha256")
            if not isinstance(metrics_sha, str) or not SHA256_RE.fullmatch(metrics_sha):
                return _blocked(f"runs.{mode}.metrics_sha256 must be a 64-character SHA-256")
            if not metrics_path.is_file() or hashlib.sha256(metrics_path.read_bytes()).hexdigest().casefold() != metrics_sha.casefold():
                return _blocked(f"runs.{mode}.metrics_json is missing or its SHA-256 does not match")
            if metrics_path.stat().st_mtime < started.timestamp() - 2.0:
                return _blocked(f"runs.{mode}.metrics_json predates this run and is stale")
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            if not isinstance(metrics, dict):
                return _blocked(f"runs.{mode}.metrics_json root must be an object")
        except (OSError, ValueError, json.JSONDecodeError) as error:
            return _blocked(str(error))

        expected_metrics = {
            "pair_id": record["pair_id"],
            "run_id": run_id,
            "rack_mode": mode,
            "backend_id": record["backend_id"],
            "route_profile": record["route_profile"],
            "source_sha256": source["sha256"],
            "source_type": source["source_type"],
            "source_sample_rate_hz": source["sample_rate_hz"],
            "source_channels": source["channels"],
            "source_wav_metadata": source_metadata,
            "model_id": model["model_id"],
            "model_revision": model["revision"],
            "model_checkpoint_sha256": model["checkpoint_sha256"],
            "route_id": route["route_id"],
            "gpu_id": hardware["gpu_id"],
            "driver_version": hardware["driver_version"],
            "audio_interface": hardware["audio_interface"],
            "audio_driver": hardware["audio_driver"],
            "input_endpoint": route["input_endpoint"],
            "output_endpoint": route["output_endpoint"],
            "output_sha256": artifacts["wav_sha256"],
            "output_wav_metadata": output_metadata,
            "paired_run_id": paired_run.get("run_id"),
            "paired_output_sha256": paired_artifacts.get("wav_sha256"),
            "paired_output_wav_metadata": paired_run.get("output_metadata"),
            "paired_e2e_first_packet_ms": paired_timing.get("e2e_first_packet_ms"),
            "delta_latency_ms": record["delta_latency_ms"],
            "timing_ms": timing,
            "continuity": continuity,
        }
        for key, expected in expected_metrics.items():
            if not _strict_json_equal(metrics.get(key), expected):
                return _blocked(f"runs.{mode}.metrics_json identity mismatch for {key}")
        if not _number(metrics.get("e2e_first_packet_ms")) or not math.isclose(
            float(metrics["e2e_first_packet_ms"]), latencies[mode], rel_tol=0, abs_tol=0.05
        ):
            return _blocked(f"runs.{mode}.metrics_json latency does not match evidence")
        verified.append({"mode": mode, "output": str(output_path), "metrics": str(metrics_path)})

    measured_delta = latencies["full_chain"] - latencies["bypass"]
    if measured_delta < 0 or not math.isclose(float(record["delta_latency_ms"]), measured_delta, rel_tol=0, abs_tol=0.05):
        return _blocked("delta_latency_ms must equal full_chain e2e_first_packet_ms minus bypass within 0.05 ms")
    if max(latencies.values()) > 5000:
        return "OFFLINE", ["paired rack output exceeds the 5000 ms LIVE budget"]

    incomplete: list[str] = []
    for mode in ("bypass", "full_chain"):
        continuity = runs[mode]["continuity"]
        if continuity["continuous_seconds"] < 60:
            incomplete.append(f"{mode} run is below the 60 s rack screening target")
        if continuity["dropouts"] or continuity["underruns"]:
            incomplete.append(f"{mode} run contains dropouts or underruns")
    if incomplete:
        return "WAITING", incomplete
    return "PASS", ["verified paired bypass/full-chain rack artifacts; this is not LIVE_GATE evidence"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify paired AetherTune audio-rack A/B evidence")
    parser.add_argument("evidence", type=Path, help="path to an audio-rack evidence JSON file")
    args = parser.parse_args()

    try:
        record = json.loads(args.evidence.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"BLOCKED: evidence file not found: {args.evidence}")
        return 2
    except (OSError, json.JSONDecodeError) as error:
        print(f"BLOCKED: cannot read evidence: {error}")
        return 2
    status, messages = classify(record, args.evidence.parent)
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
