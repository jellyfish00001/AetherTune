"""Regression tests for audio-rack WAV, hash, run-identity, and pair validation."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import wave
from pathlib import Path


_VALIDATOR_PATH = Path(__file__).with_name("audio-rack-evidence-validate.py")
_SPEC = importlib.util.spec_from_file_location("audio_rack_evidence_validate", _VALIDATOR_PATH)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


def write_wav(path: Path, samples: list[int]) -> str:
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"".join(int(value).to_bytes(2, "little", signed=True) for value in samples))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_run(root: Path, mode: str, latency_ms: float, run_id: str, group: str = "pair-001") -> tuple[dict, Path, Path]:
    source = root / "captured-source.wav"
    reference = root / "reference.wav"
    source_hash = write_wav(source, [300, -300] * 80)
    reference_hash = write_wav(reference, [200, -200] * 80)
    output = root / f"{run_id}-output.wav"
    output_hash = write_wav(output, [500 + (100 if mode == "full-chain" else 0), -500] * 80)
    metrics_path = root / f"{run_id}-metrics.json"
    metrics_path.write_text(
        json.dumps({
            "run_id": run_id,
            "wav_sha256": output_hash,
            "input_sha256": source_hash,
            "reference_sha256": reference_hash,
        }),
        encoding="utf-8",
    )
    evidence_path = root / f"{run_id}-evidence.json"
    record = {
        "schema_version": "aethertune-audio-rack/evidence-v1",
        "run_id": run_id,
        "pair_group_id": group,
        "backend_id": "seed-vc",
        "route_profile": "seed-vc-virtual-route",
        "rack_mode": mode,
        "capture": {
            "input_wav": str(source),
            "input_sha256": source_hash,
            "reference_wav": str(reference),
            "reference_sha256": reference_hash,
        },
        "timing_ms": {
            "backend_first_packet_ms": 120,
            "postfx_first_packet_ms": latency_ms,
            "routing_first_packet_ms": latency_ms,
            "e2e_first_packet_ms": latency_ms,
            "e2e_p50_ms": latency_ms,
            "e2e_p95_ms": latency_ms,
        },
        "continuity": {"continuous_seconds": 60, "dropouts": 0, "underruns": 0},
        "output_validation": {"status": "PASS", "finite": True, "non_zero": True},
        "artifacts": {
            "output_wav": str(output),
            "metrics_json": str(metrics_path),
            "wav_sha256": output_hash,
            "paired_evidence_path": "",
        },
        "delta_latency_ms": None,
    }
    return record, evidence_path, metrics_path


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aethertune-rack-evidence-") as temp_dir:
        root = Path(temp_dir)
        bypass, bypass_path, _ = build_run(root, "bypass", 120, "bypass-001")
        full, full_path, _ = build_run(root, "full-chain", 125, "full-001")
        bypass["artifacts"]["paired_evidence_path"] = str(full_path)
        bypass["delta_latency_ms"] = -5
        full["artifacts"]["paired_evidence_path"] = str(bypass_path)
        full["delta_latency_ms"] = 5
        bypass_path.write_text(json.dumps(bypass), encoding="utf-8")
        full_path.write_text(json.dumps(full), encoding="utf-8")
        assert _MODULE.classify(full, root) == ("PASS", [])

        bad_paired_delta = json.loads(full_path.read_text(encoding="utf-8"))
        bad_paired_delta["delta_latency_ms"] = 1
        full_path.write_text(json.dumps(bad_paired_delta), encoding="utf-8")
        assert _MODULE.classify(full, root)[0] == "BLOCKED"
        full_path.write_text(json.dumps(full), encoding="utf-8")

        rogue_pair_path = root / "rogue-pair.json"
        rogue_pair = json.loads(json.dumps(full))
        rogue_pair["pair_group_id"] = "rogue-group"
        rogue_pair_path.write_text(json.dumps(rogue_pair), encoding="utf-8")
        bad_reciprocal = json.loads(bypass_path.read_text(encoding="utf-8"))
        bad_reciprocal["artifacts"]["paired_evidence_path"] = str(rogue_pair_path)
        bypass_path.write_text(json.dumps(bad_reciprocal), encoding="utf-8")
        assert _MODULE.classify(full, root)[0] == "BLOCKED"
        bypass_path.write_text(json.dumps(bypass), encoding="utf-8")

        no_pair = dict(full)
        no_pair["artifacts"] = dict(full["artifacts"], paired_evidence_path="")
        assert _MODULE.classify(no_pair, root)[0] == "WAITING"

        missing_wav = json.loads(json.dumps(full))
        missing_wav["artifacts"]["output_wav"] = str(root / "not-created.wav")
        assert _MODULE.classify(missing_wav, root)[0] == "BLOCKED"

        wrong_hash = json.loads(json.dumps(full))
        wrong_hash["artifacts"]["wav_sha256"] = "0" * 64
        assert _MODULE.classify(wrong_hash, root)[0] == "BLOCKED"

        missing_metrics = json.loads(json.dumps(full))
        missing_metrics["artifacts"]["metrics_json"] = str(root / "missing-metrics.json")
        assert _MODULE.classify(missing_metrics, root)[0] == "BLOCKED"

        silent = json.loads(json.dumps(full))
        silent_path = root / "silent.wav"
        silent_hash = write_wav(silent_path, [0] * 160)
        silent["artifacts"]["output_wav"] = str(silent_path)
        silent["artifacts"]["wav_sha256"] = silent_hash
        assert _MODULE.classify(silent, root)[0] == "BLOCKED"

        bad_delta = json.loads(json.dumps(full))
        bad_delta["delta_latency_ms"] = 12
        assert _MODULE.classify(bad_delta, root)[0] == "BLOCKED"

        bad_pair = json.loads(bypass_path.read_text(encoding="utf-8"))
        bad_pair["rack_mode"] = "full-chain"
        bypass_path.write_text(json.dumps(bad_pair), encoding="utf-8")
        assert _MODULE.classify(full, root)[0] == "BLOCKED"

    print("PASS audio-rack evidence regression: WAV/hash identity, metrics identity, reciprocal paired A/B and negative cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
