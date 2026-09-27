"""Aggregate callback status and frame continuity without retaining audio samples."""

from __future__ import annotations

import math
from typing import Any


class CallbackTelemetry:
    def __init__(self, sample_rate: int) -> None:
        self.sample_rate = int(sample_rate)
        self.callbacks = 0
        self.frames = 0
        self.invalid_frame_counts = 0
        self.input_overflows = 0
        self.output_underflows = 0
        self.output_overflows = 0
        self.input_underflows = 0
        self.timestamp_callbacks = 0
        self.timestamp_discontinuities = 0
        self.max_timestamp_frame_drift = 0.0
        self.status_messages: list[str] = []
        self._previous_adc_time: float | None = None
        self._previous_frames: int | None = None

    @staticmethod
    def _flag(status: Any, name: str) -> bool:
        if isinstance(status, dict):
            return bool(status.get(name, False))
        return bool(getattr(status, name, False))

    @staticmethod
    def _adc_time(times: Any) -> float | None:
        if isinstance(times, dict):
            value = times.get("inputBufferAdcTime", times.get("input_buffer_adc_time"))
        else:
            value = getattr(times, "inputBufferAdcTime", None)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
            return float(value)
        return None

    def record(self, frames: int, times: Any, status: Any) -> None:
        self.callbacks += 1
        if not isinstance(frames, int) or frames <= 0:
            self.invalid_frame_counts += 1
        else:
            self.frames += frames

        self.input_overflows += int(self._flag(status, "input_overflow"))
        self.output_underflows += int(self._flag(status, "output_underflow"))
        self.output_overflows += int(self._flag(status, "output_overflow"))
        self.input_underflows += int(self._flag(status, "input_underflow"))
        if status and not any(
            self._flag(status, name)
            for name in ("input_overflow", "output_underflow", "output_overflow", "input_underflow", "priming_output")
        ):
            rendered = str(status)
            if rendered not in self.status_messages:
                self.status_messages.append(rendered)

        adc_time = self._adc_time(times)
        if adc_time is not None:
            self.timestamp_callbacks += 1
            if self._previous_adc_time is not None and self._previous_frames is not None:
                observed_frames = (adc_time - self._previous_adc_time) * self.sample_rate
                drift = observed_frames - self._previous_frames
                self.max_timestamp_frame_drift = max(self.max_timestamp_frame_drift, abs(drift))
                if abs(drift) > 2.0:
                    self.timestamp_discontinuities += 1
            self._previous_adc_time = adc_time
            self._previous_frames = frames if isinstance(frames, int) and frames > 0 else None

    def snapshot(self) -> dict[str, Any]:
        underruns = self.output_underflows + self.output_overflows
        timestamp_complete = self.callbacks > 0 and self.timestamp_callbacks == self.callbacks
        return {
            "callback_count": self.callbacks,
            "frames_delivered": self.frames,
            "continuous_seconds_from_frames": self.frames / self.sample_rate if self.sample_rate > 0 else 0.0,
            "invalid_frame_counts": self.invalid_frame_counts,
            "input_overflows": self.input_overflows,
            "input_underflows": self.input_underflows,
            "output_underflows": self.output_underflows,
            "output_overflows": self.output_overflows,
            "underruns": underruns,
            "timestamp_callbacks": self.timestamp_callbacks,
            "timestamp_coverage": self.timestamp_callbacks / self.callbacks if self.callbacks else 0.0,
            "timestamp_discontinuities": self.timestamp_discontinuities,
            "max_timestamp_frame_drift": self.max_timestamp_frame_drift,
            "frame_continuity_status": (
                "PASS"
                if timestamp_complete and not self.timestamp_discontinuities and not self.invalid_frame_counts
                else "WAITING"
            ),
            "status_messages": self.status_messages,
        }
