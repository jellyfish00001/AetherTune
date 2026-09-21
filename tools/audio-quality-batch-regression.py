"""Regression tests for the batch comparison status aggregation."""

from __future__ import annotations

import importlib.util
from pathlib import Path


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
print("PASS audio-quality-batch status regression")
