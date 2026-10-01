"""共用的串流 Post-FX：變聲後 EQ／壓縮／殘響，再做乾濕混合。"""
from __future__ import annotations

import math

DEFAULTS = dict(enabled=False, wet=0.3, low_db=0.0, mid_db=0.0, high_db=0.0,
                compressor_threshold_db=-18.0, compressor_ratio=3.0,
                reverb_mix=0.12, output_gain_db=0.0)
BOUNDS = dict(wet=(0, 1), low_db=(-12, 12), mid_db=(-12, 12), high_db=(-12, 12),
              compressor_threshold_db=(-48, 0), compressor_ratio=(1, 8),
              reverb_mix=(0, 0.5), output_gain_db=(-12, 6))


def validate_postfx(value=None) -> dict:
    if value is None:
        return dict(DEFAULTS)
    if not isinstance(value, dict) or set(value) - set(DEFAULTS):
        raise ValueError("PARAMETER_INVALID: Post-FX 必須是已知欄位的 object")
    settings = {**DEFAULTS, **value}
    if not isinstance(settings["enabled"], bool):
        raise ValueError("PARAMETER_INVALID: postfx.enabled 必須是 boolean")
    for key, (low, high) in BOUNDS.items():
        number = settings[key]
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number) or not low <= number <= high:
            raise ValueError(f"PARAMETER_INVALID: postfx.{key} 必須是 {low}..{high} 的有限數字")
    return settings


class PostFx:
    def __init__(self, sample_rate: int, settings=None):
        import numpy as np
        from scipy.signal import butter
        self.np = np
        self.settings = validate_postfx(settings)
        self.low = butter(1, 250, fs=sample_rate, output="sos")
        self.high = butter(1, 4000, btype="highpass", fs=sample_rate, output="sos")
        self.low_state = np.zeros((len(self.low), 2))
        self.high_state = np.zeros((len(self.high), 2))
        self.envelope = np.zeros(1)
        self.gain_state = np.zeros(1)
        self.envelope_alpha = math.exp(-1 / (0.01 * sample_rate))
        self.gain_alpha = math.exp(-1 / (0.005 * sample_rate))
        # 三條有衰減的延遲梳狀濾波器；state 跨 block 保存，無需 VST host。
        self.reverbs = []
        for seconds, feedback in ((0.0297, 0.62), (0.0371, 0.57), (0.0411, 0.53)):
            delay = round(seconds * sample_rate)
            self.reverbs.append([np.zeros(delay), 0, feedback])

    def process(self, mono):
        from scipy.signal import lfilter, sosfilt
        np, settings = self.np, self.settings
        dry = np.asarray(mono, dtype=np.float32)
        if dry.ndim != 1 or not np.isfinite(dry).all():
            raise ValueError("AUDIO_INVALID: Post-FX 只接受有限的 mono PCM")
        if not settings["enabled"] or not len(dry):
            return dry.copy()
        low, self.low_state = sosfilt(self.low, dry, zi=self.low_state)
        high, self.high_state = sosfilt(self.high, dry, zi=self.high_state)
        mid = dry - low - high
        equalized = sum(band * 10 ** (settings[key] / 20)
                        for band, key in ((low, "low_db"), (mid, "mid_db"), (high, "high_db")))
        alpha = self.envelope_alpha
        power, self.envelope = lfilter([1-alpha], [1, -alpha], equalized ** 2, zi=self.envelope)
        level = 10 * np.log10(np.maximum(power, 1e-12))
        excess = np.maximum(level - settings["compressor_threshold_db"], 0)
        reduction = excess * (1 - 1 / settings["compressor_ratio"])
        alpha = self.gain_alpha
        smooth, self.gain_state = lfilter([1-alpha], [1, -alpha], reduction, zi=self.gain_state)
        processed = equalized * 10 ** (-smooth / 20)
        if settings["reverb_mix"]:
            echoes = np.zeros(len(dry))
            for comb in self.reverbs:
                ring, cursor, feedback = comb
                result = np.empty(len(processed))
                position = 0
                # 分段向量化 circular delay，避免稀疏長 FIR 每樣本掃整條延遲線。
                while position < len(processed):
                    count = min(len(ring)-cursor, len(processed)-position)
                    delayed = ring[cursor:cursor+count].copy()
                    result[position:position+count] = delayed
                    ring[cursor:cursor+count] = (1-feedback)*processed[position:position+count] + feedback*delayed
                    position += count
                    cursor = (cursor+count) % len(ring)
                comb[1] = cursor
                echoes += result / len(self.reverbs)
            processed = (1-settings["reverb_mix"]) * processed + settings["reverb_mix"] * echoes
        mixed = dry * (1-settings["wet"]) + processed * settings["wet"]
        result = np.clip(mixed * 10 ** (settings["output_gain_db"] / 20), -1, 1).astype(np.float32)
        if not np.isfinite(result).all():
            raise ValueError("AUDIO_INVALID: Post-FX 輸出非有限")
        return result
