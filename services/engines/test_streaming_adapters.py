"""Lightweight algebra and parameter tests for resident streaming adapters."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

try:
    from .streaming_adapters import (
        XVCProcessor,
        _crossfade_overlap,
        _validate_xvc_window,
        create_processor,
    )
except ImportError:  # pragma: no cover - direct script execution
    from streaming_adapters import XVCProcessor, _crossfade_overlap, _validate_xvc_window, create_processor


class StreamingAdapterAlgebraTests(unittest.TestCase):
    def test_xvc_window_alignment_and_latency(self) -> None:
        window = _validate_xvc_window(
            {"current": 160, "chunk": 2400, "future": 80, "smooth": 20},
            16_000,
        )
        self.assertEqual(window["current"], 2_560)
        self.assertEqual(window["chunk"], 38_400)
        self.assertEqual(window["history"], 34_240)
        self.assertEqual(window["host_block"], 7_680)
        self.assertEqual(window["smooth_ms"] + window["future_ms"], 100.0)

    def test_xvc_invalid_codec_boundary_is_explicit(self) -> None:
        with self.assertRaisesRegex(ValueError, "PARAMETER_INVALID"):
            _validate_xvc_window(
                {"current": 120, "chunk": 2400, "future": 80, "smooth": 20},
                16_000,
            )

    def test_xvc_rolling_window_zero_pads_first_lookahead(self) -> None:
        processor = object.__new__(XVCProcessor)
        processor._buffer = np.arange(2_560, dtype=np.float32)
        processor._buffer_start = 0
        processor._position = 0
        processor._window = {"history": 34_240}
        window = processor._take_window(-34_240, 2_560 + 320 + 1_280)
        self.assertEqual(window.shape[0], 38_400)
        self.assertTrue(np.all(window[:34_240] == 0))
        self.assertTrue(np.all(window[34_240 : 34_240 + 2_560] == np.arange(2_560)))
        self.assertTrue(np.all(window[-1_280:] == 0))

    def test_xvc_fake_forward_waits_then_keeps_real_future(self) -> None:
        """A fake 1:1 forward proves delay and cross-block window continuity."""
        import torch

        processor = object.__new__(XVCProcessor)
        processor._window = _validate_xvc_window(
            {"current": 160, "chunk": 2400, "future": 80, "smooth": 20},
            16_000,
        )
        processor._model_sample_rate = 16_000
        processor.sample_rate = 48_000
        processor.block = int(processor._window["host_block"])
        processor._buffer = np.zeros(0, dtype=np.float32)
        processor._buffer_start = 0
        processor._received = 0
        processor._position = 0
        processor._tail = None
        processor._last_window = None
        processor._torch = torch
        processor._device = torch.device("cpu")
        processor._model = object()
        processor._speaker_condition = None
        processor._frame_condition = None
        windows = []

        class FakeForward:
            @staticmethod
            def run_stream_chunk_forward(model, source, speaker, frame):
                windows.append(source.detach().cpu().numpy().reshape(-1))
                return source

        processor._infer_utils = FakeForward
        first = processor.process(np.full(processor.block, 0.1, dtype=np.float32))
        self.assertIsNone(first)
        self.assertEqual(windows, [])

        second = processor.process(np.full(processor.block, 0.2, dtype=np.float32))
        self.assertIsNotNone(second)
        self.assertEqual(len(windows), 1)
        history = int(processor._window["history"])
        current = int(processor._window["current"])
        lookahead = windows[0][history + current :]
        self.assertGreater(float(np.mean(lookahead)), 0.15)

        third = processor.process(np.full(processor.block, 0.3, dtype=np.float32))
        self.assertIsNotNone(third)
        self.assertEqual(len(windows), 2)
        lookahead_next = windows[1][history + current :]
        self.assertGreater(float(np.mean(lookahead_next)), 0.25)
        self.assertEqual(processor._received, 3 * current)

    def test_xvc_overlap_fade_preserves_shape_and_edges(self) -> None:
        current = np.ones(8, dtype=np.float32)
        tail = np.zeros(4, dtype=np.float32)
        result = _crossfade_overlap(current, tail)
        self.assertEqual(result.shape, current.shape)
        self.assertEqual(result.dtype, np.float32)
        self.assertAlmostEqual(float(result[0]), 0.0, places=6)
        self.assertAlmostEqual(float(result[3]), 1.0, places=6)
        self.assertTrue(np.all(result[4:] == 1.0))

    def test_factory_scope_does_not_require_models_for_unknown_engine(self) -> None:
        # The factory validates the engine before any backend import.  This also
        # protects the capture worker from accidentally selecting a UI runner.
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            root.mkdir(exist_ok=True)
            with self.assertRaisesRegex(ValueError, "BACKEND_UNAVAILABLE"):
                create_processor(root, "unknown", {}, root / "reference.wav", root / "run")


if __name__ == "__main__":
    unittest.main()
