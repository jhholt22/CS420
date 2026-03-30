import threading
import time

import cv2

from util.log import log


class TelloVideoSource:
    def __init__(
        self,
        drone_interface,
        *,
        video_url: str = "udp://0.0.0.0:11111",
        warmup_s: float = 0.8,
        watchdog_s: float = 2.5,
        stall_reads: int = 20,
    ):
        self.drone = drone_interface
        self.video_url = video_url
        self.warmup_s = warmup_s
        self.watchdog_s = watchdog_s
        self.stall_reads = stall_reads

        self.cap = None
        self._started = False
        self._last_valid_ts = 0.0
        self._bad_read_streak = 0
        self._restart_lock = threading.Lock()
        self._restart_backoff_until = 0.0
        self._consec_exceptions = 0
        self._last_read_had_exception = False

    def start(self) -> bool:
        if self._started:
            return True
        return self.restart_stream()

    def _open_capture(self):
        cap = cv2.VideoCapture(self.video_url, cv2.CAP_FFMPEG)
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass
        return cap

    def _safe_read(self):
        if not self.cap:
            self._last_read_had_exception = False
            return False, None

        try:
            ok, frame = self.cap.read()
            self._last_read_had_exception = False
            return ok, frame
        except cv2.error as exc:
            self._last_read_had_exception = True
            self._consec_exceptions += 1
            log("[VIDEO]", "cap.read cv2.error", err="cv2.error", exc=repr(exc))
            return False, None
        except Exception as exc:
            self._last_read_had_exception = True
            self._consec_exceptions += 1
            log("[VIDEO]", "cap.read exception", err=type(exc).__name__, exc=repr(exc))
            return False, None

    def _wait_valid(self, max_reads: int = 120, sleep_s: float = 0.05) -> bool:
        if not self.cap:
            return False
        for _ in range(max_reads):
            ok, frame = self._safe_read()
            if ok and frame is not None and frame.size > 0:
                self._last_valid_ts = time.monotonic()
                self._bad_read_streak = 0
                self._consec_exceptions = 0
                return True
            time.sleep(sleep_s)
        return False

    def _schedule_restart(self, reason: str):
        now = time.monotonic()
        if now < self._restart_backoff_until:
            return
        if self._restart_lock.locked():
            return

        self._restart_backoff_until = now + 1.5

        def _job():
            try:
                log("[VIDEO]", "Restart scheduled", reason=reason)
                self.restart_stream()
            except Exception as exc:
                log("[VIDEO]", "restart_stream exception", err=type(exc).__name__, exc=repr(exc))

        threading.Thread(target=_job, name="video-restart", daemon=True).start()

    def restart_stream(self) -> bool:
        with self._restart_lock:
            log("[VIDEO]", "Restarting stream...")

            try:
                if self.cap:
                    self.cap.release()
            except Exception:
                pass
            self.cap = None
            self._started = False

            # Explicit stream ownership.
            try:
                self.drone.send_command("streamoff")
            except Exception:
                pass
            time.sleep(0.2)

            if not self.drone.send_command("streamon"):
                log("[VIDEO]", "streamon failed during restart")
                return False

            self.cap = self._open_capture()
            time.sleep(self.warmup_s)

            if self._wait_valid(max_reads=120):
                self._started = True
                self._consec_exceptions = 0
                log("[VIDEO]", "Tello stream ready")
                self._restart_backoff_until = time.monotonic() + 1.5
                return True

            # decoder sometimes needs a full reopen after PPS spam
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = self._open_capture()
            time.sleep(0.5)

            if self._wait_valid(max_reads=120):
                self._started = True
                self._consec_exceptions = 0
                log("[VIDEO]", "Tello stream ready after reopen")
                self._restart_backoff_until = time.monotonic() + 1.5
                return True

            log("[VIDEO]", "Restart failed, no valid frames")
            self._restart_backoff_until = time.monotonic() + 1.5
            return False

    def read(self):
        if not self.cap:
            return False, None

        if self._restart_lock.locked():
            return False, None

        ok, frame = self._safe_read()
        if ok and frame is not None and frame.size > 0:
            self._last_valid_ts = time.monotonic()
            self._bad_read_streak = 0
            self._consec_exceptions = 0
            return True, frame

        self._bad_read_streak += 1
        if self._last_read_had_exception:
            # keep consecutive exception streak for restart policy
            pass
        else:
            self._consec_exceptions = 0

        stale = (time.monotonic() - self._last_valid_ts) > self.watchdog_s if self._last_valid_ts else True
        should_restart = stale or self._bad_read_streak >= self.stall_reads or self._consec_exceptions >= 3
        if should_restart:
            log("[VIDEO]", "Frame watchdog triggered", stale=stale, bad_reads=self._bad_read_streak)
            if self._restart_lock.locked():
                return False, None
            try:
                self._schedule_restart("watchdog")
            except Exception as exc:
                log("[VIDEO]", "restart scheduling exception", err=type(exc).__name__, exc=repr(exc))

        return False, None

    def release(self):
        try:
            if self.cap:
                self.cap.release()
        except Exception:
            pass
        self.cap = None

        if self._started and getattr(self.drone, "enabled", False):
            try:
                self.drone.send_command("streamoff")
            except Exception:
                pass

        self._started = False
