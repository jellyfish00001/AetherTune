"""以真實 WAV 驗 TTS 音效、原始檔保留、聲道及取消；不開播放裝置。"""
from pathlib import Path
from threading import Event
import hashlib
import tempfile
import unittest
import numpy as np
import soundfile as sf
from .playback import PlaybackCancelled
from .postfx import render_postfx


class TtsEffectsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.source = Path(self.temp.name) / "source.wav"
        self.output = Path(self.temp.name) / "effects.wav"
        time = np.arange(24_000) / 24_000
        self.audio = np.column_stack([0.2 * np.sin(2 * np.pi * 180 * time), 0.1 * np.sin(2 * np.pi * 2200 * time)]).astype("float32")
        sf.write(self.source, self.audio, 24_000, subtype="FLOAT")
        self.source_hash = hashlib.sha256(self.source.read_bytes()).hexdigest()

    def tearDown(self):
        self.temp.cleanup()

    def test_bypass_reuses_original_without_writing(self):
        path, report = render_postfx(self.source, self.output, {"enabled": False}, Event())
        self.assertEqual(path, self.source)
        self.assertFalse(self.output.exists())
        self.assertFalse(report["enabled"])

    def test_effects_preserve_source_frames_rate_and_channels(self):
        path, report = render_postfx(self.source, self.output, {"enabled": True, "wet": 0.6, "low_db": 5, "reverb_mix": 0.25}, Event())
        rendered, rate = sf.read(path, dtype="float32", always_2d=True)
        self.assertEqual(rate, 24_000)
        self.assertEqual(rendered.shape, self.audio.shape)
        self.assertTrue(np.isfinite(rendered).all())
        self.assertGreater(float(np.max(np.abs(rendered - self.audio))), 0.01)
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), self.source_hash)
        self.assertEqual(report["source_sha256"], self.source_hash)
        self.assertNotEqual(report["source_sha256"], report["output_sha256"])

    def test_wet_zero_preserves_dry_audio(self):
        path, _ = render_postfx(self.source, self.output, {"enabled": True, "wet": 0, "low_db": 8}, Event())
        rendered, _ = sf.read(path, dtype="float32", always_2d=True)
        np.testing.assert_array_equal(rendered, self.audio)

    def test_cancel_does_not_return_playable_result(self):
        cancel = Event()
        cancel.set()
        with self.assertRaises(PlaybackCancelled):
            render_postfx(self.source, self.output, {"enabled": True}, cancel)


if __name__ == "__main__":
    unittest.main()
