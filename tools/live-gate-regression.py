"""Regression suite for the evidence-only LIVE_GATE classifier."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("live_gate_validate", ROOT / "live-gate-validate.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write_wav(path: Path, samples: list[int]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"".join(int(sample).to_bytes(2, "little", signed=True) for sample in samples))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(root: Path, first_packet: float = 120.0) -> dict:
    source = root / "mic.wav"
    reference = root / "reference.wav"
    output = root / "routed-output.wav"
    source_hash = write_wav(source, [500, -500] * 80)
    reference_hash = write_wav(reference, [300, -300] * 80)
    output_hash = write_wav(output, [800, -800] * 80)
    return {
        "schema_version": "aethertune-live-gate/v1",
        "run_id": "regression-001",
        "backend_id": "seed-vc-realtime-tiny",
        "route_profile": "seed-vc-virtual-route",
        "hardware": {"gpu": "fixture"},
        "capture": {
            "device": "fixture-microphone",
            "host_api": "fixture-host-api",
            "sample_rate_hz": 16000,
            "channels": 1,
            "input_wav": str(source),
            "input_sha256": source_hash,
            "reference_wav": str(reference),
            "reference_sha256": reference_hash,
        },
        "timing_ms": {
            "capture_to_backend_first_packet_ms": 40.0,
            "backend_first_packet_ms": 80.0,
            "postfx_first_packet_ms": 90.0,
            "routing_first_packet_ms": 110.0,
            "e2e_first_packet_ms": first_packet,
            "e2e_p50_ms": first_packet,
            "e2e_p95_ms": first_packet,
        },
        "continuity": {"continuous_seconds": 600.0, "dropouts": 0, "underruns": 0},
        "output_validation": {
            "status": "PASS",
            "finite": True,
            "non_zero": True,
            "output_wav": str(output),
            "wav_sha256": output_hash,
        },
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aethertune-live-gate-") as temp_dir:
        root = Path(temp_dir)
        cases: list[tuple[str, dict, str]] = []
        valid = record(root)
        cases.append(("LIVE", valid, "LIVE"))

        long_wav = root / "long-valid.wav"
        long_hash = write_wav(long_wav, [1, -1] * 10000)
        long_report = MODULE.validate_wav(long_wav)
        if long_report["sha256"] != long_hash or not long_report["non_zero"] or long_report["frames"] != 20000:
            raise AssertionError("long PCM WAV validation did not consume the full declared artifact")

        offline = record(root, first_packet=5000.1)
        cases.append(("OFFLINE", offline, "OFFLINE"))

        waiting = record(root)
        waiting["output_validation"] = {"status": "WAITING"}
        cases.append(("WAITING", waiting, "WAITING"))

        missing_output = record(root)
        missing_output["output_validation"]["output_wav"] = str(root / "missing.wav")
        cases.append(("MISSING_OUTPUT_FILE", missing_output, "BLOCKED"))

        mismatched_hash = record(root)
        mismatched_hash["output_validation"]["wav_sha256"] = "0" * 64
        cases.append(("OUTPUT_HASH_MISMATCH", mismatched_hash, "BLOCKED"))

        silent_output = record(root)
        silent_path = root / "silent.wav"
        silent_hash = write_wav(silent_path, [0] * 160)
        silent_output["output_validation"].update(output_wav=str(silent_path), wav_sha256=silent_hash)
        cases.append(("SILENT_OUTPUT", silent_output, "BLOCKED"))

        missing_capture = record(root)
        missing_capture["capture"]["input_wav"] = str(root / "missing-mic.wav")
        cases.append(("MISSING_CAPTURE_FILE", missing_capture, "BLOCKED"))

        silent_capture = record(root)
        silent_mic = root / "silent-mic.wav"
        silent_capture_hash = write_wav(silent_mic, [0] * 160)
        silent_capture["capture"].update(input_wav=str(silent_mic), input_sha256=silent_capture_hash)
        cases.append(("SILENT_CAPTURE", silent_capture, "BLOCKED"))

        silent_reference = record(root)
        silent_ref = root / "silent-reference.wav"
        silent_reference_hash = write_wav(silent_ref, [0] * 160)
        silent_reference["capture"].update(reference_wav=str(silent_ref), reference_sha256=silent_reference_hash)
        cases.append(("SILENT_REFERENCE", silent_reference, "BLOCKED"))

        malformed = record(root)
        del malformed["timing_ms"]
        cases.append(("MISSING_TIMING", malformed, "BLOCKED"))

        for name, payload, expected in cases:
            status, _ = MODULE.classify(payload, artifact_root=root)
            if status != expected:
                raise AssertionError(f"{name}: expected {expected}, got {status}")

        evidence = root / "evidence.json"
        evidence.write_text(json.dumps(valid, ensure_ascii=False), encoding="utf-8")
        status, _ = MODULE.classify(json.loads(evidence.read_text(encoding="utf-8")), artifact_root=root)
        if status != "LIVE":
            raise AssertionError(f"temporary JSON case: expected LIVE, got {status}")

    print("PASS live-gate regression: real WAV/hash identity, silent inputs/outputs, WAITING, OFFLINE, BLOCKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
