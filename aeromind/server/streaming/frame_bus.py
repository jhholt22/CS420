from __future__ import annotations

import threading
import time
from typing import Any


class FrameBus:
    """
    Thread-safe latest-frame holder + simple FPS/age metrics.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._frame: Any = None
        self._ts: float = 0.0

        self._count = 0
        self._last_fps_check = time.time()
        self._fps = 0.0

    def publish(self, frame: Any) -> None:
        now = time.time()

        with self._lock:
            self._frame = frame
            self._ts = now
            self._count += 1

            elapsed = now - self._last_fps_check
            if elapsed >= 1.0:
                self._fps = self._count / elapsed
                self._count = 0
                self._last_fps_check = now

    def get_latest(self) -> tuple[Any, float]:
        with self._lock:
            return self._frame, self._ts

    def frame_age_ms(self) -> int:
        with self._lock:
            if self._ts == 0:
                return -1
            return int((time.time() - self._ts) * 1000)

    def fps_estimate(self) -> float:
        with self._lock:
            return self._fps