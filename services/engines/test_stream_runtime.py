"""音訊 queue 的 frame 邊界與 bounded backlog regression。"""
import unittest
import numpy as np
from services.engines.stream_runtime import SampleFifo


class SampleFifoTests(unittest.TestCase):
    def test_variable_backend_chunks_remain_contiguous(self):
        fifo = SampleFifo(20)
        fifo.push(np.arange(3))
        fifo.push(np.arange(3, 11))
        np.testing.assert_array_equal(fifo.pop(6), np.arange(6))
        self.assertIsNone(fifo.pop(6))
        np.testing.assert_array_equal(fifo.pop(6, partial=True), np.arange(6, 11))
        self.assertEqual(fifo.frames, 0)

    def test_slow_backend_cannot_create_unbounded_delay(self):
        fifo = SampleFifo(10)
        for start in (0, 4, 8, 12):
            fifo.push(np.arange(start, start+4))
        np.testing.assert_array_equal(fifo.pop(10), np.arange(6, 16))
        self.assertEqual(fifo.dropped, 6)

    def test_callback_empty_output_does_not_block(self):
        fifo = SampleFifo(10)
        self.assertEqual(len(fifo.pop(960, partial=True)), 0)


if __name__ == '__main__':
    unittest.main()
