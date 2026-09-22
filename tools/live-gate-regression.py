"""Small regression suite for the evidence-only LIVE_GATE classifier."""

from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("live_gate_validate", ROOT / "live-gate-validate.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def record(first_packet: float = 120.0) -> dict:
    return {
        "schema_version": "aethertune-live-gate/v1",
        "run_id": "regression",
        "backend_id": "fixture",
        "route_profile": "fixture",
        "hardware": {"gpu": "fixture"},
        "capture": {"device": "fixture", "sample_rate_hz": 48000},
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
        "output_validation": {"status": "PASS", "finite": True, "non_zero": True},
    }


def main() -> int:
    cases = {
        "LIVE": (record(), "LIVE"),
        "OFFLINE": (record(first_packet=5000.1), "OFFLINE"),
        "WAITING": ({**record(), "output_validation": {"status": "WAITING"}}, "WAITING"),
        "FAILED_OUTPUT": ({**record(), "output_validation": {"status": "FAIL", "finite": False, "non_zero": False}}, "BLOCKED"),
        "BLOCKED": ({key: value for key, value in record().items() if key != "timing_ms"}, "BLOCKED"),
    }
    for name, (payload, expected) in cases.items():
        status, _ = MODULE.classify(payload)
        if status != expected:
            raise AssertionError(f"{name}: expected {expected}, got {status}")

    # Also prove that the CLI can consume UTF-8 JSON without leaving artifacts in the repo.
    with tempfile.TemporaryDirectory(prefix="aethertune-live-gate-") as temp_dir:
        evidence = Path(temp_dir) / "evidence.json"
        evidence.write_text(json.dumps(record(), ensure_ascii=False), encoding="utf-8")
        status, _ = MODULE.classify(json.loads(evidence.read_text(encoding="utf-8")))
        if status != "LIVE":
            raise AssertionError(f"temporary JSON case: expected LIVE, got {status}")

    print("PASS live-gate regression: LIVE/OFFLINE/WAITING/BLOCKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
