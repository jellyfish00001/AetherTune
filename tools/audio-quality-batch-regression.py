"""Regression tests for the batch comparison status aggregation."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "audio-quality-batch.py"
spec = importlib.util.spec_from_file_location("audio_quality_batch", MODULE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load {MODULE_PATH}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def rows(*statuses: str) -> list[dict[str, object]]:
    return [
        {
            "backend": "RVC",
            "status": status,
            "duration_sec": 1.0,
            "sample_rate": 24000,
            "rms_dbfs": -20.0,
            "peak_dbfs": -10.0,
            "clipping_ratio": 0.0,
        }
        for status in statuses
    ]


assert module.summarize(rows("PASS", "PASS"))[0]["status"] == "PASS"
assert module.summarize(rows("PASS", "DEGRADED"))[0]["status"] == "DEGRADED"
assert module.summarize(rows("PASS", "BLOCKED"))[0]["status"] == "BLOCKED"
assert module.summarize(rows("BLOCKED"))[0]["blocked"] == 1


BACKENDS = ["RVC", "Seed-VC", "CosyVoice2", "Breeze TTS 2"]


def run_main(status_by_backend: dict[str, str], records: list[tuple[str, str, Path]] | None = None) -> tuple[int, dict[str, object]]:
    selected = records if records is not None else [
        (backend, "case", Path(f"{index}.wav"))
        for index, backend in enumerate(BACKENDS)
    ]

    def fake_measure(path: Path, backend: str, case: str) -> dict[str, object]:
        return {
            "backend": backend,
            "case": case,
            "path": str(path),
            "status": status_by_backend.get(backend, "PASS"),
            "sample_rate": 24000,
            "duration_sec": 1.0,
            "rms_dbfs": -20.0,
            "peak_dbfs": -10.0,
            "clipping_ratio": 0.0,
        }

    with tempfile.TemporaryDirectory(prefix="aethertune-quality-regression-") as temp_dir:
        argv = ["audio-quality-batch.py", "--output-dir", temp_dir]
        with patch.object(module, "build_records", return_value=selected), patch.object(module, "measure", side_effect=fake_measure), patch.object(sys, "argv", argv):
            exit_code = module.main()
        report = json.loads((Path(temp_dir) / "audio-quality-comparison.json").read_text(encoding="utf-8"))
    return exit_code, report


exit_code, report = run_main({})
assert (exit_code, report["status"]) == (0, "PASS")
exit_code, report = run_main({"Seed-VC": "DEGRADED"})
assert (exit_code, report["status"]) == (0, "DEGRADED")
exit_code, report = run_main({"Seed-VC": "BLOCKED"})
assert (exit_code, report["status"]) == (1, "BLOCKED")
missing_backend_records = [
    (backend, "case", Path(f"{index}.wav"))
    for index, backend in enumerate(BACKENDS[:3])
]
exit_code, report = run_main({}, missing_backend_records)
assert (exit_code, report["status"]) == (1, "BLOCKED")
exit_code, report = run_main({}, [])
assert (exit_code, report["status"]) == (1, "BLOCKED")
print("PASS audio-quality-batch status regression")
