"""LatencyTrace 單元測試；僅標準函式庫。"""

import json
import tempfile
import unittest
from pathlib import Path

from services.engines.latency_trace import LatencyTrace


class LatencyTraceTests(unittest.TestCase):
    def test_disabled_is_noop(self):
        trace = LatencyTrace(False)
        trace.record_input(480, 480)
        trace.record_model_done(480, 480)
        self.assertEqual(trace.rows(), [])
        self.assertEqual(trace.summary()["enabled"], False)

    def test_enabled_bounded_maxlen(self):
        trace = LatencyTrace(True, maxlen=3)
        for i in range(5):
            trace.record_input((i + 1) * 480, 480)
        self.assertEqual(len(trace.rows()), 3)

    def test_summary_frame_positions_synthetic(self):
        trace = LatencyTrace(True)
        base = 1_000_000_000
        ms10 = 10_000_000
        ms30 = 30_000_000
        ms60 = 60_000_000
        trace.record_input(480, 480, base)
        trace.record_input(960, 480, base + ms10)
        trace.record_model_done(480, 480, base + ms30)
        trace.record_output_written(480, 480, base + ms60)
        trace.record_model_done(960, 480, base + ms10 + ms30)
        trace.record_output_written(960, 480, base + ms10 + ms60)
        summary = trace.summary()
        self.assertTrue(summary["enabled"])
        self.assertEqual(summary["note"], "approximate_internal, not acoustic E2E")
        self.assertAlmostEqual(summary["input_to_model_ms"]["p50_ms"], 30.0, delta=0.5)
        self.assertAlmostEqual(summary["input_to_output_ms"]["p50_ms"], 60.0, delta=0.5)
        self.assertEqual(summary["input_to_model_ms"]["max_ms"], 30.0)
        self.assertEqual(summary["input_to_output_ms"]["max_ms"], 60.0)

    def test_write_jsonl(self):
        trace = LatencyTrace(True)
        trace.record_input(960, 480, 42)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "latency-trace.jsonl"
            trace.write_jsonl(path)
            lines = path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 1)
            row = json.loads(lines[0])
            self.assertEqual(row["event"], "input")
            self.assertEqual(row["frame_pos"], 960)
            self.assertNotIn("chunk_id", row)


if __name__ == "__main__":
    unittest.main()