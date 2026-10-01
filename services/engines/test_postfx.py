"""Post-FX 的訊號／block 連續性 regression，不代表實體音訊驗收。"""
import unittest
import numpy as np
from services.engines.postfx import PostFx, validate_postfx


class PostFxTests(unittest.TestCase):
    def test_bypass_and_dry_are_exact(self):
        samples = np.linspace(-.8, .8, 2400, dtype=np.float32)
        np.testing.assert_array_equal(PostFx(48000).process(samples), samples)
        np.testing.assert_array_equal(PostFx(48000, dict(enabled=True, wet=0)).process(samples), samples)

    def test_chunk_boundaries_preserve_filter_history(self):
        samples = np.random.default_rng(17).normal(0, .15, 9600).astype(np.float32)
        settings = dict(enabled=True, wet=.7, low_db=4, high_db=-3, reverb_mix=.3)
        full = PostFx(48000, settings).process(samples)
        rack = PostFx(48000, settings)
        blocks = np.concatenate([rack.process(block) for block in np.split(samples, 10)])
        np.testing.assert_allclose(blocks, full, atol=1e-6)
        self.assertFalse(np.allclose(full, samples))

    def test_reverb_has_tail_and_limiter_is_finite(self):
        rack = PostFx(48000, dict(enabled=True, wet=1, reverb_mix=.5, compressor_ratio=1))
        impulse = np.zeros(4800, dtype=np.float32)
        impulse[0] = .5
        output = rack.process(impulse)
        self.assertGreater(float(np.max(np.abs(output[1000:]))), .01)
        output = PostFx(48000, dict(enabled=True, output_gain_db=6)).process(np.ones(960, dtype=np.float32) * 4)
        self.assertTrue(np.isfinite(output).all())
        self.assertLessEqual(float(np.max(np.abs(output))), 1)

    def test_bad_settings_fail_before_stream_start(self):
        for value in (False, dict(enabled=1), dict(wet=float('nan')), dict(low_db=13), dict(unknown=0)):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_postfx(value)


if __name__ == '__main__':
    unittest.main()
