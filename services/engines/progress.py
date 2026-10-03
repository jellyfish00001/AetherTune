"""程序存活與真實階段分開回報；heartbeat 不偽裝成模型進度。"""
from __future__ import annotations
from datetime import datetime, timezone
import threading
import time


class Progress:
    def __init__(self, request_id=None):
        self.lock = threading.RLock()
        self.started = time.monotonic()
        self.updated = self.started
        self.phase = "environment"
        self.request_id = request_id
        self.load_seconds = None
        self.runtime_reused = False

    def set(self, phase, *, load_seconds=None, runtime_reused=None):
        with self.lock:
            if phase != self.phase:
                self.phase = phase
                self.updated = time.monotonic()
            if load_seconds is not None:
                self.load_seconds = float(load_seconds)
            if runtime_reused is not None:
                self.runtime_reused = bool(runtime_reused)

    def snapshot(self, worker_alive=None):
        with self.lock:
            now = time.monotonic()
            return {"phase": self.phase, "elapsed_seconds": max(0, now - self.started),
                    "last_progress_seconds_ago": max(0, now - self.updated),
                    "observed_at": datetime.now(timezone.utc).isoformat(),
                    "worker_alive": worker_alive, "request_id": self.request_id,
                    "load_seconds": self.load_seconds, "runtime_reused": self.runtime_reused}
