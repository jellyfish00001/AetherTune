"""Regression tests for audio-rack evidence classification."""

from __future__ import annotations

import importlib.util
from pathlib import Path


_VALIDATOR_PATH = Path(__file__).with_name("audio-rack-evidence-validate.py")
_SPEC = importlib.util.spec_from_file_location("audio_rack_evidence_validate", _VALIDATOR_PATH)
if _SPEC is None or _SPEC.loader is None:  # pragma: no cover - repository layout failure
    raise RuntimeError(f"cannot load validator: {_VALIDATOR_PATH}")
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
classify = _MODULE.classify


def base_record() -> dict:
    return {
        "schema_version": "aethertune-audio-rack/evidence-v1",
        "run_id": "regression",
        "backend_id": "seed-vc",
        "route_profile": "seed-vc-virtual-route",
        "rack_mode": "bypass",
        "timing_ms": {
            "backend_first_packet_ms": 120,
            "postfx_first_packet_ms": 125,
            "routing_first_packet_ms": 130,
            "e2e_first_packet_ms": 140,
            "e2e_p50_ms": 145,
            "e2e_p95_ms": 190,
        },
        "continuity": {"continuous_seconds": 60, "dropouts": 0, "underruns": 0},
        "output_validation": {"status": "PASS", "finite": True, "non_zero": True},
        "artifacts": {
            "output_wav": "artifacts/example.wav",
            "metrics_json": "artifacts/example.json",
            "wav_sha256": "0" * 64,
        },
        "delta_latency_ms": 5,
    }


def main() -> int:
    record = base_record()
    status, _ = classify(record)
    assert status == "PASS"

    waiting = base_record()
    waiting["delta_latency_ms"] = None
    status, _ = classify(waiting)
    assert status == "WAITING"

    offline = base_record()
    offline["timing_ms"]["e2e_first_packet_ms"] = 5001
    status, _ = classify(offline)
    assert status == "OFFLINE"

    blocked = base_record()
    blocked["artifacts"]["wav_sha256"] = "bad"
    status, _ = classify(blocked)
    assert status == "BLOCKED"
    print("PASS audio-rack evidence regression: PASS/WAITING/OFFLINE/BLOCKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
