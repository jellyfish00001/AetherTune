"""降噪的音訊行為與連續性驗收；不代表實體麥克風聽感。"""
import json
from pathlib import Path
import unittest
import numpy as np
from services.engines.noise_reduction import NoiseReduction, validate_noise_reduction
from services.engines.progress import Progress


class NoiseReductionTests(unittest.TestCase):
    def test_bypass_is_exact(self):
        samples = np.random.default_rng(7).normal(0, .05, 9703).astype(np.float32)
        for settings in ({}, {"enabled": True, "strength_db": 0}):
            nr = NoiseReduction(settings=settings)
            np.testing.assert_array_equal(nr.process(samples), samples)
            self.assertEqual(nr.delay_frames, 0)

    def test_variable_blocks_are_contiguous(self):
        samples = np.random.default_rng(7).normal(0, .05, 9703).astype(np.float32)
        full = NoiseReduction(settings={"enabled": True}).process(samples)
        nr = NoiseReduction(settings={"enabled": True})
        pieces = []
        cursor = 0
        for size in (13, 417, 300, 960, 1600, 23, 6390):
            pieces.append(nr.process(samples[cursor:cursor + size]))
            cursor += size
        np.testing.assert_allclose(np.concatenate(pieces), full, atol=1e-7)
        self.assertEqual(nr.delay_frames, 960)
        self.assertLessEqual(len(nr.pending), nr.hop)

    def test_silence_and_invalid_input(self):
        nr = NoiseReduction(settings={"enabled": True})
        np.testing.assert_array_equal(nr.process_file(np.zeros(1607, dtype=np.float32)), np.zeros(1607))
        for samples in (np.array([float('nan')]), np.zeros((10, 2))):
            with self.assertRaises(ValueError):
                nr.process(samples)
        for settings in (False, {"enabled": 1}, {"strength_db": 25}, {"strength_db": float('inf')}, {"extra": 1}):
            with self.assertRaises(ValueError):
                validate_noise_reduction(settings)

    def test_noisy_speech_and_tail(self):
        import soundfile as sf
        from scipy.signal import resample_poly
        import math
        root = Path(__file__).resolve().parents[2]
        speech, rate = sf.read(root / "dataset/reference-voices/voice-male-m1.wav", dtype="float32", always_2d=True)
        speech = speech.mean(axis=1)
        if rate != 48000:
            divisor = math.gcd(rate, 48000)
            speech = resample_poly(speech, 48000 // divisor, rate // divisor).astype(np.float32)
        padding = np.zeros(48000, dtype=np.float32)
        clean = np.concatenate((padding, speech, padding))
        noise = np.random.default_rng(20261003).normal(0, .008, len(clean)).astype(np.float32)
        nr = NoiseReduction(settings={"enabled": True, "strength_db": 12})
        rendered = nr.process_file(clean + noise)
        self.assertEqual(len(rendered), len(clean))
        self.assertTrue(np.isfinite(rendered).all())
        rms = lambda x: float(np.sqrt(np.mean(np.asarray(x, dtype=np.float64) ** 2)))
        noise_reduction = 20 * np.log10(rms(noise[24000:48000]) / rms(rendered[24000:48000]))
        voiced = np.abs(speech) > .02
        loss = 20 * np.log10(rms(speech[voiced]) / rms(rendered[48000:48000 + len(speech)][voiced]))
        stream = NoiseReduction(settings={"enabled": True, "strength_db": 12})
        # 以 20ms callback 重跑同一 fixture，補償固定延遲後須與整檔處理一致。
        chunks = [stream.process((clean + noise)[start:start + 960]) for start in range(0, len(clean), 960)]
        chunks.append(stream.process(np.zeros(stream.delay_frames + stream.hop, dtype=np.float32)))
        streamed = np.concatenate(chunks)[stream.delay_frames:stream.delay_frames + len(clean)]
        np.testing.assert_allclose(streamed, rendered, atol=1e-7)
        report = {"noise_reduction_db": float(noise_reduction), "voice_energy_loss_db": float(loss),
                  "frames": len(rendered), "finite": True, **nr.metrics(), "callback_20ms": stream.metrics()}
        folder = root / "artifacts/desktop/audio-tuning-20261003"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "denoise-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        sf.write(folder / "noisy-source.wav", clean + noise, 48000)
        sf.write(folder / "denoised-source.wav", rendered, 48000)
        self.assertGreaterEqual(noise_reduction, 6, report)
        self.assertLess(abs(loss), 3, report)
        # 排出尾端後，最後一段來源語音仍存在且沒有 frame 遺失。
        self.assertGreater(rms(rendered[48000 + len(speech) - 4800:48000 + len(speech)]), 1e-5)

    def test_heartbeat_does_not_claim_phase_progress(self):
        from unittest.mock import patch
        with patch('services.engines.progress.time.monotonic', side_effect=[0, 2, 3, 8, 10]):
            progress = Progress('request-a')
            progress.set('model_load')
            first = progress.snapshot(True)
            progress.set('model_load')
            second = progress.snapshot(True)
        self.assertEqual(first['last_progress_seconds_ago'], 1)
        self.assertEqual(second['last_progress_seconds_ago'], 6)
        self.assertEqual(second['elapsed_seconds'], 8)
        self.assertEqual(second['request_id'], 'request-a')


if __name__ == '__main__':
    unittest.main()
