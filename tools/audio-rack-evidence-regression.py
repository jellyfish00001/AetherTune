"""Negative regressions for paired rack artifacts, identity, timing, and LIVE separation."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import soundfile as sf


TOOLS = Path(__file__).resolve().parent


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:  # pragma: no cover - repository layout failure
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RACK = load_module("audio_rack_evidence_validate", TOOLS / "audio-rack-evidence-validate.py")
LIVE = load_module("live_gate_validate", TOOLS / "live-gate-validate.py")


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


def tone(*, silent: bool = False) -> np.ndarray:
    if silent:
        return np.zeros(4800, dtype=np.float32)
    return (0.1 * np.sin(np.arange(4800, dtype=np.float32) * 2.0 * np.pi * 440 / 48000)).astype(np.float32)


def record(root: Path) -> dict:
    started = datetime.now(timezone.utc) - timedelta(seconds=1)
    source_path = root / "source.wav"
    sf.write(source_path, tone(), 48000)
    source_hash = sha256(source_path)
    source_metadata = wav_metadata(source_path)
    pair = {
        "schema_version": "aethertune-audio-rack/evidence-v1",
        "pair_id": "pair-20260926-001",
        "backend_id": "seed-vc",
        "route_profile": "seed-vc-cable-to-b1",
        "source": {
            "wav": "source.wav",
            "sha256": source_hash,
            "source_type": "synthetic_callback",
            "sample_rate_hz": source_metadata["sample_rate_hz"],
            "channels": source_metadata["channels"],
        },
        "model": {
            "model_id": "seed-vc-realtime-tiny",
            "revision": "51383efd921027683c89e5348211d93ff12ac2a8",
            "checkpoint_sha256": "1" * 64,
        },
        "hardware": {
            "gpu": "RTX 5060 Ti",
            "gpu_id": "GPU-0",
            "driver_version": "fixture-driver",
            "audio_interface": "fixture-interface",
            "audio_driver": "MME",
        },
        "route": {
            "route_id": "seed-vc-to-b1",
            "input_endpoint": "CABLE Output",
            "output_endpoint": "Voicemeeter Out B1",
            "audio_driver": "MME",
        },
        "runs": {},
        "delta_latency_ms": 35.0,
    }
    for mode, latency in (("bypass", 220.0), ("full_chain", 255.0)):
        run_id = f"{mode}-run-001"
        output_name = f"{mode}.wav"
        metrics_name = f"{mode}.json"
        output_path = root / output_name
        sf.write(output_path, tone() * (0.8 if mode == "bypass" else 0.7), 48000)
        output_metadata = wav_metadata(output_path)
        artifacts = {
            "output_wav": output_name,
            "wav_sha256": sha256(output_path),
            "metrics_json": metrics_name,
        }
        pair["runs"][mode] = {
            "run_id": run_id,
            "started_at_utc": started.isoformat(),
            "rack_mode": mode,
            "output_metadata": output_metadata,
            "timing_ms": {
                "backend_first_packet_ms": 120,
                "postfx_first_packet_ms": 130 if mode == "full_chain" else 125,
                "routing_first_packet_ms": 150 if mode == "full_chain" else 145,
                "e2e_first_packet_ms": latency,
                "e2e_p50_ms": latency + 5,
                "e2e_p95_ms": latency + 20,
            },
            "continuity": {"continuous_seconds": 60, "dropouts": 0, "underruns": 0},
            "output_validation": {"status": "PASS", "finite": True, "non_zero": True},
            "artifacts": artifacts,
        }

    for mode in ("bypass", "full_chain"):
        run = pair["runs"][mode]
        paired_mode = "full_chain" if mode == "bypass" else "bypass"
        paired_run = pair["runs"][paired_mode]
        paired_output = root / paired_run["artifacts"]["output_wav"]
        metrics_path = root / run["artifacts"]["metrics_json"]
        metrics = {
            "pair_id": pair["pair_id"],
            "run_id": run["run_id"],
            "rack_mode": mode,
            "backend_id": pair["backend_id"],
            "route_profile": pair["route_profile"],
            "source_sha256": source_hash,
            "source_type": pair["source"]["source_type"],
            "source_sample_rate_hz": pair["source"]["sample_rate_hz"],
            "source_channels": pair["source"]["channels"],
            "source_wav_metadata": source_metadata,
            "model_id": pair["model"]["model_id"],
            "model_revision": pair["model"]["revision"],
            "model_checkpoint_sha256": pair["model"]["checkpoint_sha256"],
            "route_id": pair["route"]["route_id"],
            "gpu_id": pair["hardware"]["gpu_id"],
            "driver_version": pair["hardware"]["driver_version"],
            "audio_interface": pair["hardware"]["audio_interface"],
            "audio_driver": pair["hardware"]["audio_driver"],
            "input_endpoint": pair["route"]["input_endpoint"],
            "output_endpoint": pair["route"]["output_endpoint"],
            "output_sha256": run["artifacts"]["wav_sha256"],
            "output_wav_metadata": run["output_metadata"],
            "e2e_first_packet_ms": run["timing_ms"]["e2e_first_packet_ms"],
            "paired_run_id": paired_run["run_id"],
            "paired_output_sha256": sha256(paired_output),
            "paired_output_wav_metadata": paired_run["output_metadata"],
            "paired_e2e_first_packet_ms": paired_run["timing_ms"]["e2e_first_packet_ms"],
            "delta_latency_ms": pair["delta_latency_ms"],
            "timing_ms": run["timing_ms"],
            "continuity": run["continuity"],
        }
        metrics_path.write_text(json.dumps(metrics), encoding="utf-8")
        run["artifacts"]["metrics_sha256"] = sha256(metrics_path)
    return pair


def expect(name: str, payload: dict, root: Path, expected: str) -> None:
    actual, messages = RACK.classify(payload, root)
    if actual != expected:
        raise AssertionError(f"{name}: expected {expected}, got {actual}: {messages}")


def rewrite_metrics(payload: dict, root: Path, mode: str, update) -> None:
    """Edit one fixture metrics file and refresh its artifact hash to test semantics."""
    path = root / payload["runs"][mode]["artifacts"]["metrics_json"]
    metrics = json.loads(path.read_text(encoding="utf-8"))
    update(metrics)
    path.write_text(json.dumps(metrics), encoding="utf-8")
    payload["runs"][mode]["artifacts"]["metrics_sha256"] = sha256(path)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aethertune-rack-evidence-") as temp_dir:
        root = Path(temp_dir)
        base = record(root)
        expect("valid paired technical fixture", base, root, "PASS")

        unpaired = json.loads(json.dumps(base))
        del unpaired["runs"]["full_chain"]
        expect("unpaired run", unpaired, root, "WAITING")

        missing = json.loads(json.dumps(base))
        missing["runs"]["full_chain"]["artifacts"]["output_wav"] = "missing.wav"
        expect("missing output WAV", missing, root, "BLOCKED")

        hash_mismatch = json.loads(json.dumps(base))
        hash_mismatch["runs"]["bypass"]["artifacts"]["wav_sha256"] = "0" * 64
        expect("output hash mismatch", hash_mismatch, root, "BLOCKED")

        route_mismatch = json.loads(json.dumps(base))
        route_mismatch["route"]["route_id"] = "different-route"
        expect("route identity mismatch", route_mismatch, root, "BLOCKED")

        invalid_source_type = json.loads(json.dumps(base))
        invalid_source_type["source"]["source_type"] = "unknown-source"
        expect("invalid source type", invalid_source_type, root, "BLOCKED")

        outer_source_rate_mismatch = json.loads(json.dumps(base))
        outer_source_rate_mismatch["source"]["sample_rate_hz"] = 44100
        expect("outer source sample rate mismatch", outer_source_rate_mismatch, root, "BLOCKED")

        outer_source_channels_mismatch = json.loads(json.dumps(base))
        outer_source_channels_mismatch["source"]["channels"] = 2
        expect("outer source channel mismatch", outer_source_channels_mismatch, root, "BLOCKED")

        source_metrics_root = root / "source-metrics-metadata-mismatch"
        source_metrics_root.mkdir()
        source_metrics_mismatch = record(source_metrics_root)
        rewrite_metrics(
            source_metrics_mismatch,
            source_metrics_root,
            "bypass",
            lambda metrics: metrics["source_wav_metadata"].__setitem__("sample_rate_hz", 44100),
        )
        expect("metrics-only source WAV metadata mismatch", source_metrics_mismatch, source_metrics_root, "BLOCKED")

        output_metadata_root = root / "output-metadata-mismatch"
        output_metadata_root.mkdir()
        output_metadata_mismatch = record(output_metadata_root)
        output_metadata_mismatch["runs"]["full_chain"]["output_metadata"]["channels"] = 2
        expect("outer output metadata mismatch", output_metadata_mismatch, output_metadata_root, "BLOCKED")

        output_metrics_root = root / "output-metrics-metadata-mismatch"
        output_metrics_root.mkdir()
        output_metrics_mismatch = record(output_metrics_root)
        rewrite_metrics(
            output_metrics_mismatch,
            output_metrics_root,
            "full_chain",
            lambda metrics: metrics["output_wav_metadata"].__setitem__("sample_rate_hz", 44100),
        )
        expect("metrics-only output WAV metadata mismatch", output_metrics_mismatch, output_metrics_root, "BLOCKED")

        source_header_root = root / "source-header-rehashed"
        source_header_root.mkdir()
        source_header_changed = record(source_header_root)
        changed_source = source_header_root / "source.wav"
        sf.write(changed_source, tone(), 44100)
        changed_source_hash = sha256(changed_source)
        source_header_changed["source"]["sha256"] = changed_source_hash
        source_header_changed["source"]["sample_rate_hz"] = 44100
        for mode in ("bypass", "full_chain"):
            rewrite_metrics(
                source_header_changed,
                source_header_root,
                mode,
                lambda metrics: metrics.__setitem__("source_sha256", changed_source_hash),
            )
        expect("source WAV header changed with refreshed file hash", source_header_changed, source_header_root, "BLOCKED")

        output_header_root = root / "output-header-rehashed"
        output_header_root.mkdir()
        output_header_changed = record(output_header_root)
        changed_output = output_header_root / "bypass.wav"
        sf.write(changed_output, tone() * 0.8, 44100)
        changed_output_hash = sha256(changed_output)
        output_header_changed["runs"]["bypass"]["artifacts"]["wav_sha256"] = changed_output_hash
        output_header_changed["runs"]["bypass"]["output_metadata"] = wav_metadata(changed_output)
        rewrite_metrics(
            output_header_changed,
            output_header_root,
            "bypass",
            lambda metrics: metrics.__setitem__("output_sha256", changed_output_hash),
        )
        expect("output WAV header changed with refreshed file hash", output_header_changed, output_header_root, "BLOCKED")

        timing_root = root / "timing-mismatch"
        timing_root.mkdir()
        timing_mismatch = record(timing_root)
        rewrite_metrics(
            timing_mismatch,
            timing_root,
            "full_chain",
            lambda metrics: metrics["timing_ms"].__setitem__("e2e_p95_ms", metrics["timing_ms"]["e2e_p95_ms"] + 1),
        )
        expect("metrics timing mismatch", timing_mismatch, timing_root, "BLOCKED")

        continuity_root = root / "continuity-mismatch"
        continuity_root.mkdir()
        continuity_mismatch = record(continuity_root)
        rewrite_metrics(
            continuity_mismatch,
            continuity_root,
            "bypass",
            lambda metrics: metrics["continuity"].__setitem__("dropouts", 1),
        )
        expect("metrics continuity mismatch", continuity_mismatch, continuity_root, "BLOCKED")

        pair_identity_root = root / "pair-identity-mismatch"
        pair_identity_root.mkdir()
        pair_identity_mismatch = record(pair_identity_root)
        rewrite_metrics(
            pair_identity_mismatch,
            pair_identity_root,
            "full_chain",
            lambda metrics: metrics.__setitem__("paired_run_id", "unrelated-run"),
        )
        expect("metrics paired identity mismatch", pair_identity_mismatch, pair_identity_root, "BLOCKED")

        pair_output_root = root / "pair-output-mismatch"
        pair_output_root.mkdir()
        pair_output_mismatch = record(pair_output_root)
        rewrite_metrics(
            pair_output_mismatch,
            pair_output_root,
            "bypass",
            lambda metrics: metrics.__setitem__("paired_output_sha256", "0" * 64),
        )
        expect("metrics paired output hash mismatch", pair_output_mismatch, pair_output_root, "BLOCKED")

        metrics_delta_root = root / "metrics-delta-mismatch"
        metrics_delta_root.mkdir()
        metrics_delta_mismatch = record(metrics_delta_root)
        for mode in ("bypass", "full_chain"):
            rewrite_metrics(
                metrics_delta_mismatch,
                metrics_delta_root,
                mode,
                lambda metrics: metrics.__setitem__("delta_latency_ms", 12.0),
            )
        expect("metrics delta mismatch", metrics_delta_mismatch, metrics_delta_root, "BLOCKED")

        stale_identity = json.loads(json.dumps(base))
        metrics_path = root / "full_chain.json"
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        metrics["run_id"] = "old-run"
        metrics_path.write_text(json.dumps(metrics), encoding="utf-8")
        stale_identity["runs"]["full_chain"]["artifacts"]["metrics_sha256"] = sha256(metrics_path)
        expect("stale run identity", stale_identity, root, "BLOCKED")

        delta_root = root / "delta-mismatch"
        delta_root.mkdir()
        delta_mismatch = record(delta_root)
        delta_mismatch["delta_latency_ms"] = 12
        for mode in ("bypass", "full_chain"):
            rewrite_metrics(
                delta_mismatch,
                delta_root,
                mode,
                lambda metrics: metrics.__setitem__("delta_latency_ms", 12.0),
            )
        expect("delta latency mismatch", delta_mismatch, delta_root, "BLOCKED")

        offline_root = root / "offline"
        offline_root.mkdir()
        over_budget = record(offline_root)
        over_budget["runs"]["full_chain"]["timing_ms"]["e2e_first_packet_ms"] = 5001
        over_budget["delta_latency_ms"] = 4781
        rewrite_metrics(
            over_budget,
            offline_root,
            "full_chain",
            lambda metrics: (
                metrics.__setitem__("e2e_first_packet_ms", 5001),
                metrics["timing_ms"].__setitem__("e2e_first_packet_ms", 5001),
                metrics.__setitem__("delta_latency_ms", 4781),
            ),
        )
        rewrite_metrics(
            over_budget,
            offline_root,
            "bypass",
            lambda metrics: (
                metrics.__setitem__("paired_e2e_first_packet_ms", 5001),
                metrics.__setitem__("delta_latency_ms", 4781),
            ),
        )
        expect("over five seconds", over_budget, offline_root, "OFFLINE")

        silent_root = root / "silent"
        silent_root.mkdir()
        silent = record(silent_root)
        silent_wav = silent_root / "full_chain.wav"
        sf.write(silent_wav, tone(silent=True), 48000)
        silent["runs"]["full_chain"]["artifacts"]["wav_sha256"] = sha256(silent_wav)
        silent_metrics_path = silent_root / "full_chain.json"
        silent_metrics = json.loads(silent_metrics_path.read_text(encoding="utf-8"))
        silent_metrics["output_sha256"] = silent["runs"]["full_chain"]["artifacts"]["wav_sha256"]
        silent_metrics_path.write_text(json.dumps(silent_metrics), encoding="utf-8")
        silent["runs"]["full_chain"]["artifacts"]["metrics_sha256"] = sha256(silent_metrics_path)
        expect("zero output WAV", silent, silent_root, "BLOCKED")

        # Rack evidence is deliberately insufficient for LIVE_GATE: this fixture contains
        # generated tones and has no physical-microphone capture/human-review contract.
        live_root = root / "live-separation"
        live_root.mkdir()
        live_only_waiting = record(live_root)
        live_status, _ = LIVE.classify(live_only_waiting, live_root)
        if live_status != "WAITING":
            raise AssertionError(f"rack fixture must not classify as LIVE: got {live_status}")

    print("PASS audio-rack evidence regression: synthetic paired fixture PASS only for rack; source type/header and source/output metrics metadata mismatches BLOCKED; rehashed WAV header changes BLOCKED; timing/continuity/pair/delta mismatches BLOCKED; unpaired WAITING; missing/hash/identity/silent BLOCKED; >5s OFFLINE; LIVE_GATE WAITING")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
