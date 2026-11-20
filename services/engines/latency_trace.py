"""Bounded perf_counter latency trace for stream runtime; stdlib only."""

from __future__ import annotations

import bisect
import json
import os
import time
from collections import deque
from pathlib import Path
from typing import Any


def trace_enabled(request: dict | None) -> bool:
    if request and request.get("latency_trace"):
        return True
    return os.environ.get("AETHERTUNE_LATENCY_TRACE") == "1"


class LatencyTrace:
    """Frame-position latency trace (48 kHz host frame counters).

    Events use cumulative frame positions, not per-callback chunk ids:
    - ``record_input(end_frame_pos, ...)``: host input frames accumulated after this callback.
    - ``record_model_done(consumed_input_frame_pos, ...)``: cumulative input frames the worker
      had consumed when this inference block finished.
    - ``record_output_written(cumulative_output_frame_pos, ...)``: cumulative non-empty output
      frames written.

    ``summary()`` pairs model/output positions with input timelines via ``bisect`` on input
    events. ``input_to_output_ms`` assumes output frame index *k* aligns with input frame *k*
    (ignores model rolling context, lookahead, and startup buffer fill). That is
    **approximate internal** pipeline delay only; acoustic pulse bench E2E remains authoritative.
  """

    __slots__ = ("enabled", "_maxlen", "_rows")

    def __init__(self, enabled: bool, *, maxlen: int = 20000) -> None:
        self.enabled = bool(enabled)
        self._maxlen = int(maxlen)
        self._rows: deque[tuple[str, int, int, int]] | None = (
            deque(maxlen=self._maxlen) if self.enabled else None
        )

    @classmethod
    def for_request(cls, request: dict | None, *, maxlen: int = 20000) -> LatencyTrace:
        return cls(trace_enabled(request), maxlen=maxlen)

    def record_input(self, end_frame_pos: int, frames: int, t_ns: int | None = None) -> None:
        if not self.enabled or self._rows is None:
            return
        self._rows.append(
            ("input", int(end_frame_pos), int(frames), t_ns if t_ns is not None else time.perf_counter_ns())
        )

    def record_model_done(
        self, consumed_input_frame_pos: int, produced_frames: int, t_ns: int | None = None
    ) -> None:
        if not self.enabled or self._rows is None:
            return
        self._rows.append(
            (
                "model_done",
                int(consumed_input_frame_pos),
                int(produced_frames),
                t_ns if t_ns is not None else time.perf_counter_ns(),
            )
        )

    def record_output_written(
        self, cumulative_output_frame_pos: int, frames: int, t_ns: int | None = None
    ) -> None:
        if not self.enabled or self._rows is None:
            return
        self._rows.append(
            (
                "output_written",
                int(cumulative_output_frame_pos),
                int(frames),
                t_ns if t_ns is not None else time.perf_counter_ns(),
            )
        )

    def rows(self) -> list[tuple[str, int, int, int]]:
        if not self.enabled or self._rows is None:
            return []
        return list(self._rows)

    def _input_timeline(self) -> tuple[list[int], list[int]]:
        positions: list[int] = []
        times: list[int] = []
        for kind, frame_pos, _frames, t_ns in self._rows or ():
            if kind == "input":
                positions.append(frame_pos)
                times.append(t_ns)
        return positions, times

    @staticmethod
    def _time_at_or_after(positions: list[int], times: list[int], target: int) -> int | None:
        if not positions:
            return None
        idx = bisect.bisect_left(positions, target)
        if idx >= len(positions):
            return None
        return times[idx]

    def _latencies_ms(self) -> dict[str, list[float]]:
        if not self.enabled or not self._rows:
            return {"input_to_model_ms": [], "input_to_output_ms": []}
        in_pos, in_times = self._input_timeline()
        input_to_model: list[float] = []
        input_to_output: list[float] = []
        for kind, frame_pos, _extra, t_ns in self._rows:
            if kind == "model_done":
                t_in = self._time_at_or_after(in_pos, in_times, frame_pos)
                if t_in is not None:
                    input_to_model.append((t_ns - t_in) / 1_000_000.0)
            elif kind == "output_written":
                t_in = self._time_at_or_after(in_pos, in_times, frame_pos)
                if t_in is not None:
                    input_to_output.append((t_ns - t_in) / 1_000_000.0)
        return {"input_to_model_ms": input_to_model, "input_to_output_ms": input_to_output}

    @staticmethod
    def _percentile(values: list[float], p: float) -> float | None:
        if not values:
            return None
        ordered = sorted(values)
        if len(ordered) == 1:
            return ordered[0]
        rank = (len(ordered) - 1) * (p / 100.0)
        lo = int(rank)
        hi = min(lo + 1, len(ordered) - 1)
        frac = rank - lo
        return ordered[lo] * (1.0 - frac) + ordered[hi] * frac

    @staticmethod
    def _stats_block(values: list[float]) -> dict[str, Any]:
        if not values:
            return {"count": 0, "p50_ms": None, "p95_ms": None, "max_ms": None}
        return {
            "count": len(values),
            "p50_ms": LatencyTrace._percentile(values, 50),
            "p95_ms": LatencyTrace._percentile(values, 95),
            "max_ms": max(values),
        }

    def summary(self) -> dict[str, Any]:
        if not self.enabled:
            return {"enabled": False, "count": 0}
        lat = self._latencies_ms()
        return {
            "enabled": True,
            "count": len(self.rows()),
            "note": "approximate_internal, not acoustic E2E",
            "input_to_model_ms": self._stats_block(lat["input_to_model_ms"]),
            "input_to_output_ms": self._stats_block(lat["input_to_output_ms"]),
        }

    def write_jsonl(self, path: Path) -> None:
        if not self.enabled or self._rows is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as stream:
            for kind, frame_pos, frames, t_ns in self._rows:
                stream.write(
                    json.dumps(
                        {"event": kind, "frame_pos": frame_pos, "frames": frames, "t_ns": t_ns},
                        ensure_ascii=False,
                    )
                    + "\n"
                )