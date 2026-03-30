import threading
import time


class FrameBus:
    def __init__(self):
        self._lock = threading.Lock()
        self._frame = None
        self._ts = 0.0
        self._seq = 0
        self._fps_window = []

    def publish(self, frame):
        now = time.monotonic()
        with self._lock:
            self._frame = frame
            self._ts = now
            self._seq += 1
            self._fps_window.append(now)
            cutoff = now - 2.0
            while self._fps_window and self._fps_window[0] < cutoff:
                self._fps_window.pop(0)

    def latest(self):
        with self._lock:
            return self._frame, self._ts, self._seq

    def frame_age_ms(self) -> int | None:
        with self._lock:
            if self._ts <= 0:
                return None
            return int((time.monotonic() - self._ts) * 1000)

    def fps_estimate(self) -> float:
        with self._lock:
            if len(self._fps_window) < 2:
                return 0.0
            span = self._fps_window[-1] - self._fps_window[0]
            if span <= 0:
                return 0.0
            return (len(self._fps_window) - 1) / span
