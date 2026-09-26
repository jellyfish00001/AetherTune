"""Negative regression cases for live-gate artifact, source, and identity checks."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import soundfile as sf


ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("live_gate_validate", ROOT / "live-gate-validate.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wav_metadata(path: Path) -> dict:
    info = sf.info(path)
    return {
        "sample_rate_hz": int(info.samplerate),
        "channels": int(info.channels),
        "frames": int(info.frames),
        "duration_sec": int(info.frames) / int(info.samplerate),
    }


def record(root: Path, *, silent_output: bool = False) -> dict:
    started = datetime.now(timezone.utc) - timedelta(seconds=2)
    samples = np.sin(np.arange(4800) * 2.0 * np.pi * 440 / 48000).astype(np.float32) * 0.1
    input_path = root / "input.wav"
    output_path = root / "output.wav"
    sf.write(input_path, samples, 48000)
    sf.write(output_path, np.zeros_like(samples) if silent_output else samples * 0.8, 48000)

    result = {
        "schema_version": "aethertune-live-gate/v1",
        "run_id": "run-regression-001",
        "run_started_at_utc": started.isoformat(),
        "backend_id": "seed-vc",
        "route_profile": "seed-vc-cable-to-b1",
        "model": {
            "model_id": "seed-vc-realtime-tiny",
            "revision": "51383efd921027683c89e5348211d93ff12ac2a8",
            "checkpoint_sha256": "1" * 64,
        },
        "hardware": {
            "gpu": "RTX 5060 Ti",
            "gpu_id": "GPU-0",
            "driver_version": "test-driver",
            "audio_interface": "PortAudio endpoint",
            "audio_driver": "MME",
        },
        "capture": {
            "source_type": "physical_microphone",
            "device_name": "Microphone endpoint",
            "device_id": "device-001",
            "sample_rate_hz": 48000,
            "channels": 1,
        },
        "route": {
            "route_id": "route-seed-vc-b1",
            "input_endpoint": "Microphone endpoint",
            "output_endpoint": "Voicemeeter Out B1",
            "audio_driver": "MME",
        },
        "timing_ms": {
            "capture_to_backend_first_packet_ms": 100,
            "backend_first_packet_ms": 120,
            "postfx_first_packet_ms": 130,
            "routing_first_packet_ms": 150,
            "e2e_first_packet_ms": 220,
            "e2e_p50_ms": 240,
            "e2e_p95_ms": 300,
        },
        "continuity": {"continuous_seconds": 600, "dropouts": 0, "underruns": 0},
        "output_validation": {"status": "PASS", "finite": True, "non_zero": True, **wav_metadata(output_path)},
        "artifacts": {
            "input_wav": "input.wav",
            "input_sha256": sha256(input_path),
            "output_wav": "output.wav",
            "output_sha256": sha256(output_path),
            "metrics_json": "metrics.json",
        },
        "human_review": {"status": "WAITING", "review_id": ""},
    }
    metrics = {
        "run_id": result["run_id"],
        "backend_id": result["backend_id"],
        "route_profile": result["route_profile"],
        "model_id": result["model"]["model_id"],
        "model_revision": result["model"]["revision"],
        "model_checkpoint_sha256": result["model"]["checkpoint_sha256"],
        "source_sha256": result["artifacts"]["input_sha256"],
        "output_sha256": result["artifacts"]["output_sha256"],
        "route_id": result["route"]["route_id"],
        "gpu_id": result["hardware"]["gpu_id"],
        "driver_version": result["hardware"]["driver_version"],
        "audio_interface": result["hardware"]["audio_interface"],
        "audio_driver": result["hardware"]["audio_driver"],
        "capture_device_id": result["capture"]["device_id"],
        "capture_source_type": result["capture"]["source_type"],
        "capture_sample_rate_hz": result["capture"]["sample_rate_hz"],
        "capture_channels": result["capture"]["channels"],
        "input_wav_metadata": wav_metadata(input_path),
        "output_wav_metadata": wav_metadata(output_path),
        "input_endpoint": result["route"]["input_endpoint"],
        "output_endpoint": result["route"]["output_endpoint"],
        "timing_ms": result["timing_ms"],
        "continuity": result["continuity"],
        "human_review": result["human_review"],
    }
    metrics_path = root / "metrics.json"
    metrics_path.write_text(json.dumps(metrics), encoding="utf-8")
    result["artifacts"]["metrics_sha256"] = sha256(metrics_path)
    return result


def expect(name: str, payload: dict, root: Path, expected: str) -> None:
    actual, messages = MODULE.classify(payload, root)
    if actual != expected:
        raise AssertionError(f"{name}: expected {expected}, got {actual}: {messages}")


def rebind_metrics(root: Path, payload: dict, update) -> None:
    path = root / payload["artifacts"]["metrics_json"]
    metrics = json.loads(path.read_text(encoding="utf-8"))
    update(metrics)
    path.write_text(json.dumps(metrics), encoding="utf-8")
    payload["artifacts"]["metrics_sha256"] = sha256(path)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aethertune-live-gate-") as temp_dir:
        root = Path(temp_dir)
        base = record(root)
        expect("human review pending", base, root, "LIVE_CANDIDATE")

        synthetic = json.loads(json.dumps(base))
        synthetic["capture"]["source_type"] = "synthetic_callback"
        expect("outer-only synthetic capture source type", synthetic, root, "WAITING")

        missing_human_review = json.loads(json.dumps(base))
        del missing_human_review["human_review"]
        expect("missing human review record", missing_human_review, root, "WAITING")

        source_metrics_root = root / "source-type-mismatch"
        source_metrics_root.mkdir()
        source_metrics_mismatch = record(source_metrics_root)
        rebind_metrics(
            source_metrics_root,
            source_metrics_mismatch,
            lambda metrics: metrics.__setitem__("capture_source_type", "synthetic_callback"),
        )
        expect("metrics capture source type mismatch", source_metrics_mismatch, source_metrics_root, "BLOCKED")

        capture_rate_mismatch = json.loads(json.dumps(base))
        capture_rate_mismatch["capture"]["sample_rate_hz"] = 44100
        expect("outer capture sample rate mismatch", capture_rate_mismatch, root, "BLOCKED")

        capture_channels_mismatch = json.loads(json.dumps(base))
        capture_channels_mismatch["capture"]["channels"] = 2
        expect("outer capture channel mismatch", capture_channels_mismatch, root, "BLOCKED")

        input_metrics_root = root / "input-metrics-metadata-mismatch"
        input_metrics_root.mkdir()
        input_metrics_mismatch = record(input_metrics_root)
        rebind_metrics(
            input_metrics_root,
            input_metrics_mismatch,
            lambda metrics: metrics["input_wav_metadata"].__setitem__("channels", 2),
        )
        expect("metrics-only input WAV metadata mismatch", input_metrics_mismatch, input_metrics_root, "BLOCKED")

        input_bool_metrics_root = root / "input-bool-metadata"
        input_bool_metrics_root.mkdir()
        input_bool_metrics = record(input_bool_metrics_root)
        rebind_metrics(
            input_bool_metrics_root,
            input_bool_metrics,
            lambda metrics: metrics["input_wav_metadata"].__setitem__("channels", True),
        )
        expect("metrics bool channel is not integer one", input_bool_metrics, input_bool_metrics_root, "BLOCKED")

        output_metrics_root = root / "output-metrics-metadata-mismatch"
        output_metrics_root.mkdir()
        output_metrics_mismatch = record(output_metrics_root)
        rebind_metrics(
            output_metrics_root,
            output_metrics_mismatch,
            lambda metrics: metrics["output_wav_metadata"].__setitem__("sample_rate_hz", 44100),
        )
        expect("metrics-only output WAV metadata mismatch", output_metrics_mismatch, output_metrics_root, "BLOCKED")

        input_header_root = root / "input-header-rehashed"
        input_header_root.mkdir()
        input_header_changed = record(input_header_root)
        changed_input_path = input_header_root / "input.wav"
        sf.write(changed_input_path, np.zeros(4800, dtype=np.float32) + 0.05, 44100)
        changed_input_hash = sha256(changed_input_path)
        input_header_changed["artifacts"]["input_sha256"] = changed_input_hash
        input_header_changed["capture"]["sample_rate_hz"] = 44100
        rebind_metrics(input_header_root, input_header_changed, lambda metrics: metrics.__setitem__("source_sha256", changed_input_hash))
        expect("input WAV header changed with refreshed file hash", input_header_changed, input_header_root, "BLOCKED")

        output_header_root = root / "output-header-rehashed"
        output_header_root.mkdir()
        output_header_changed = record(output_header_root)
        changed_output_path = output_header_root / "output.wav"
        sf.write(changed_output_path, np.full(4800, 0.05, dtype=np.float32), 44100)
        changed_output_hash = sha256(changed_output_path)
        output_header_changed["artifacts"]["output_sha256"] = changed_output_hash
        output_header_changed["output_validation"].update(wav_metadata(changed_output_path))
        rebind_metrics(output_header_root, output_header_changed, lambda metrics: metrics.__setitem__("output_sha256", changed_output_hash))
        expect("output WAV header changed with refreshed file hash", output_header_changed, output_header_root, "BLOCKED")

        missing_audio = json.loads(json.dumps(base))
        missing_audio["artifacts"]["output_wav"] = "missing-output.wav"
        expect("missing output file", missing_audio, root, "BLOCKED")

        stale = json.loads(json.dumps(base))
        stale["run_started_at_utc"] = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        expect("stale output", stale, root, "BLOCKED")

        mismatch = json.loads(json.dumps(base))
        mismatch["artifacts"]["output_sha256"] = "0" * 64
        expect("output hash mismatch", mismatch, root, "BLOCKED")

        model_mismatch = json.loads(json.dumps(base))
        model_mismatch["model"]["revision"] = "different-revision"
        expect("model identity mismatch", model_mismatch, root, "BLOCKED")

        route_mismatch = json.loads(json.dumps(base))
        route_mismatch["route"]["route_id"] = "different-route"
        expect("route identity mismatch", route_mismatch, root, "BLOCKED")

        hardware_mismatch = json.loads(json.dumps(base))
        hardware_mismatch["hardware"]["gpu_id"] = "GPU-1"
        expect("hardware identity mismatch", hardware_mismatch, root, "BLOCKED")

        timing_mismatch = json.loads(json.dumps(base))
        timing_mismatch["timing_ms"]["e2e_p95_ms"] += 1
        expect("metrics timing mismatch", timing_mismatch, root, "BLOCKED")

        continuity_mismatch = json.loads(json.dumps(base))
        continuity_mismatch["continuity"]["dropouts"] += 1
        expect("metrics continuity mismatch", continuity_mismatch, root, "BLOCKED")

        bool_counter = json.loads(json.dumps(base))
        bool_counter["continuity"]["dropouts"] = False
        expect("boolean dropouts is not integer zero", bool_counter, root, "BLOCKED")

        human_identity_mismatch = json.loads(json.dumps(base))
        human_identity_mismatch["human_review"]["review_id"] = "different-fixture-review"
        expect("metrics human review identity mismatch", human_identity_mismatch, root, "BLOCKED")

        human_hash_mismatch = json.loads(json.dumps(base))
        human_hash_mismatch["human_review"]["input_sha256"] = "2" * 64
        expect("metrics human review hash mismatch", human_hash_mismatch, root, "BLOCKED")

        human_ratings_mismatch = json.loads(json.dumps(base))
        human_ratings_mismatch["human_review"]["ratings"] = {"fixture_rating": 1}
        expect("metrics human review ratings mismatch", human_ratings_mismatch, root, "BLOCKED")

        review_root = root / "incomplete-human-review"
        review_root.mkdir()
        incomplete_review = record(review_root)
        incomplete_review["human_review"] = {
            "status": "PASS",
            "review_id": "fixture-review-id",
            "reviewer_id": "fixture-reviewer-id",
            "reviewed_at_utc": datetime.now(timezone.utc).isoformat(),
            "input_sha256": incomplete_review["artifacts"]["input_sha256"],
            "output_sha256": incomplete_review["artifacts"]["output_sha256"],
        }
        rebind_metrics(review_root, incomplete_review, lambda metrics: metrics.__setitem__("human_review", incomplete_review["human_review"]))
        expect("PASS human review without ratings", incomplete_review, review_root, "BLOCKED")

        review_hash_root = root / "human-review-hash-mismatch"
        review_hash_root.mkdir()
        review_hash_mismatch = record(review_hash_root)
        review_hash_mismatch["human_review"] = {
            "status": "PASS",
            "review_id": "fixture-review-id",
            "reviewer_id": "fixture-reviewer-id",
            "reviewed_at_utc": datetime.now(timezone.utc).isoformat(),
            "input_sha256": "2" * 64,
            "output_sha256": review_hash_mismatch["artifacts"]["output_sha256"],
            "ratings": {key: 3 for key in MODULE.REQUIRED_HUMAN_RATINGS},
        }
        rebind_metrics(review_hash_root, review_hash_mismatch, lambda metrics: metrics.__setitem__("human_review", review_hash_mismatch["human_review"]))
        expect("PASS human review with wrong WAV hash", review_hash_mismatch, review_hash_root, "BLOCKED")

        future_metrics = json.loads(json.dumps(base))
        metrics_path = root / "metrics.json"
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        metrics["run_id"] = "old-run"
        metrics_path.write_text(json.dumps(metrics), encoding="utf-8")
        future_metrics["artifacts"]["metrics_sha256"] = sha256(metrics_path)
        expect("stale metrics run id", future_metrics, root, "BLOCKED")

        stale_file_root = root / "stale-metrics"
        stale_file_root.mkdir()
        stale_file = record(stale_file_root)
        stale_metrics_path = stale_file_root / "metrics.json"
        old_timestamp = (datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()
        os.utime(stale_metrics_path, (old_timestamp, old_timestamp))
        stale_file["artifacts"]["metrics_sha256"] = sha256(stale_metrics_path)
        expect("stale metrics file timestamp", stale_file, stale_file_root, "BLOCKED")

        silent_root = root / "silent"
        silent_root.mkdir()
        silent = record(silent_root, silent_output=True)
        expect("zero output", silent, silent_root, "BLOCKED")

        offline_root = root / "offline"
        offline_root.mkdir()
        offline = record(offline_root)
        offline["timing_ms"]["e2e_first_packet_ms"] = 5000.1
        offline_metrics_path = offline_root / "metrics.json"
        offline_metrics = json.loads(offline_metrics_path.read_text(encoding="utf-8"))
        offline_metrics["timing_ms"]["e2e_first_packet_ms"] = 5000.1
        offline_metrics_path.write_text(json.dumps(offline_metrics), encoding="utf-8")
        offline["artifacts"]["metrics_sha256"] = sha256(offline_metrics_path)
        expect("over budget", offline, offline_root, "OFFLINE")

    print("PASS live-gate regression: synthetic source WAITING; outer-only and metrics identity/timing/continuity/human review/WAV metadata mismatches BLOCKED; bool-as-integer counters/metadata rejected; rehashed header changes BLOCKED; incomplete PASS review BLOCKED; pending review CANDIDATE; >5s OFFLINE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
