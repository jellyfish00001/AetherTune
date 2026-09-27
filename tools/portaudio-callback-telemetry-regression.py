"""Regression cases for Seed-VC callback status and frame-continuity telemetry."""

from __future__ import annotations

import importlib.util
from pathlib import Path


PATH = Path(__file__).with_name("portaudio-callback-telemetry.py")
SPEC = importlib.util.spec_from_file_location("portaudio_callback_telemetry", PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def main() -> int:
    telemetry = MODULE.CallbackTelemetry(16000)
    telemetry.record(480, {"inputBufferAdcTime": 1.0}, {})
    telemetry.record(
        480,
        {"inputBufferAdcTime": 1.03},
        {"input_overflow": True, "output_underflow": True},
    )
    report = telemetry.snapshot()
    assert report["callback_count"] == 2
    assert report["frames_delivered"] == 960
    assert report["continuous_seconds_from_frames"] == 0.06
    assert report["input_overflows"] == 1
    assert report["output_underflows"] == 1
    assert report["underruns"] == 1
    assert report["timestamp_discontinuities"] == 0
    assert report["frame_continuity_status"] == "PASS"

    gap = MODULE.CallbackTelemetry(16000)
    gap.record(480, {"inputBufferAdcTime": 1.0}, {})
    gap.record(480, {"inputBufferAdcTime": 1.10}, {})
    assert gap.snapshot()["timestamp_discontinuities"] == 1
    assert gap.snapshot()["frame_continuity_status"] == "WAITING"

    unavailable = MODULE.CallbackTelemetry(16000)
    unavailable.record(480, {}, {})
    assert unavailable.snapshot()["frame_continuity_status"] == "WAITING"
    print("PASS PortAudio callback telemetry regression: status flags, frames, timestamp gaps, missing timestamps")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
