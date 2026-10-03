"""變聲前的因果頻譜降噪；48 kHz mono、20 ms 窗、10 ms hop。

狀態跨區塊保留，最大抑制量限制語音誤傷。不是 noise gate 或語音分離模型。
"""
from __future__ import annotations

import math
import time

DEFAULTS = {"enabled": False, "strength_db": 12.0}


def validate_noise_reduction(value=None) -> dict:
    if value is None:
        return dict(DEFAULTS)
    if not isinstance(value, dict) or set(value) - set(DEFAULTS):
        raise ValueError("PARAMETER_INVALID: noise_reduction 必須是已知欄位的 object")
    settings = {**DEFAULTS, **value}
    strength = settings["strength_db"]
    if not isinstance(settings["enabled"], bool):
        raise ValueError("PARAMETER_INVALID: noise_reduction.enabled 必須是 boolean")
    if isinstance(strength, bool) or not isinstance(strength, (int, float)) or not math.isfinite(strength) or not 0 <= strength <= 24:
        raise ValueError("PARAMETER_INVALID: noise_reduction.strength_db 必須是 0..24 的有限數字")
    return settings


class NoiseReduction:
    def __init__(self, sample_rate=48000, settings=None):
        import numpy as np
        from scipy.signal import check_NOLA
        self.np = np
        self.settings = validate_noise_reduction(settings)
        self.active = self.settings["enabled"] and self.settings["strength_db"] > 0
        self.hop = round(sample_rate * .01)
        self.window_size = 2 * self.hop
        self.delay_frames = self.window_size if self.active else 0
        self.sample_rate = sample_rate
        self.window = np.sqrt(np.hanning(self.window_size + 1)[:-1])
        if not check_NOLA(self.window, self.window_size, self.hop):
            raise ValueError("AUDIO_INVALID: 降噪窗不符合 NOLA")
        self.reset()

    def reset(self):
        np = self.np
        self.pending = np.empty(0, dtype=np.float32)
        # 一個 hop 的輸出保留加上 WOLA 自身一個 hop，固定總延遲為 20 ms。
        self.output = np.zeros(self.hop, dtype=np.float32)
        self.analysis = np.zeros(self.window_size)
        self.overlap = np.zeros(self.window_size)
        self.normalizer = np.zeros(self.window_size)
        self.power = None
        self.noise = None
        self.gain = np.ones(self.hop + 1)
        self.frames = 0
        self.seconds = 0.0
        self.calls = 0
        self.max_call_seconds = 0.0

    def _frame(self, samples):
        np, hop = self.np, self.hop
        self.analysis[:-hop] = self.analysis[hop:]
        self.analysis[-hop:] = samples
        spectrum = np.fft.rfft(self.analysis * self.window)
        power = np.abs(spectrum) ** 2
        self.power = power if self.power is None else .8 * self.power + .2 * power
        if self.noise is None:
            self.noise = self.power.copy()
        else:
            # 慢速上升、快速追蹤局部低點；持續底噪可估計，避免快速把語音學成噪音。
            flatness = float(np.exp(np.mean(np.log(power + 1e-12))) / (np.mean(power) + 1e-12))
            if flatness > .4 and np.mean(power) < 3 * np.mean(self.noise):
                self.noise = .9 * self.noise + .1 * power
            else:
                self.noise = np.minimum(self.noise * 1.001 + 1e-12, self.power * 3)
        floor = 10 ** (-self.settings["strength_db"] / 20)
        target = np.sqrt(np.maximum(1 - 2 * self.noise / (power + 1e-12), floor ** 2))
        target = np.convolve(np.pad(target, (2, 2), mode="edge"), np.ones(5) / 5, mode="valid")
        # 語音起音快速放行、抑制緩慢增加，減少水聲、顫抖和接縫。
        alpha = np.where(target > self.gain, .2, .85)
        self.gain = alpha * self.gain + (1 - alpha) * target
        reconstructed = np.fft.irfft(spectrum * self.gain, n=self.window_size) * self.window
        self.overlap += reconstructed
        self.normalizer += self.window ** 2
        result = self.overlap[:hop] / np.maximum(self.normalizer[:hop], 1e-12)
        self.overlap[:-hop] = self.overlap[hop:]
        self.overlap[-hop:] = 0
        self.normalizer[:-hop] = self.normalizer[hop:]
        self.normalizer[-hop:] = 0
        self.frames += 1
        return result.astype(np.float32)

    def process(self, mono):
        np = self.np
        samples = np.asarray(mono, dtype=np.float32)
        if samples.ndim != 1 or not np.isfinite(samples).all():
            raise ValueError("AUDIO_INVALID: 降噪只接受有限 mono PCM")
        if not self.active or not len(samples):
            return samples.copy()
        started = time.perf_counter()
        self.pending = np.concatenate((self.pending, samples))
        chunks = []
        cursor = 0
        while len(self.pending) - cursor >= self.hop:
            chunks.append(self._frame(self.pending[cursor:cursor + self.hop]))
            cursor += self.hop
        self.pending = self.pending[cursor:]
        if chunks:
            self.output = np.concatenate((self.output, *chunks))
        result = self.output[:len(samples)].copy()
        self.output = self.output[len(samples):]
        if len(result) != len(samples) or not np.isfinite(result).all():
            raise ValueError("AUDIO_INVALID: 降噪輸出長度或樣本無效")
        elapsed = time.perf_counter() - started
        self.seconds += elapsed
        self.max_call_seconds = max(self.max_call_seconds, elapsed)
        self.calls += 1
        return result

    def process_file(self, mono):
        """離線來源排出 WOLA 尾端並補償自身延遲；不裁掉語音尾音。"""
        np = self.np
        samples = np.asarray(mono, dtype=np.float32)
        result = self.process(samples)
        if not self.active or not len(samples):
            return result
        tail = self.process(np.zeros(self.delay_frames + self.hop, dtype=np.float32))
        return np.concatenate((result, tail))[self.delay_frames:self.delay_frames + len(samples)]

    def metrics(self):
        return {"noise_reduction_enabled": bool(self.active), "noise_reduction_seconds": self.seconds,
                "noise_reduction_max_call_ms": self.max_call_seconds * 1000,
                "noise_reduction_delay_ms": self.delay_frames / self.sample_rate * 1000}
