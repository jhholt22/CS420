from __future__ import annotations

import threading
import time
from typing import Any
from urllib.parse import urlencode

import cv2

from server.core.util.log import log


class TelloVideoSource:
    def __init__(
        self,
        drone,
        video_url: str,
        warmup_s: float = 0.8,
        watchdog_s: float = 2.5,
        stall_reads: int = 20,
    ):
        self.drone = drone
        self.video_url = video_url
        self.warmup_s = warmup_s
        self.watchdog_s = watchdog_s
        self.stall_reads = stall_reads

        self.cap: cv2.VideoCapture | None = None
        self._failed_reads = 0
        self._logged_first_frame = False
        self._stopping = False
        self._live = False
        self._last_no_frame_log = 0.0
        self._last_restart_ts = 0.0
        self._restart_lock = threading.Lock()
        self._stream_enabled = False
        self._reconnect_failures = 0
        self._capture_open_attempts = 0

        self._startup_open_attempts = 3
        self._first_frame_attempts = 30
        self._first_frame_delay_s = 0.10
        self._restart_backoff_s = max(0.75, watchdog_s / 2.0)
        self._status_log_interval_s = 2.0
        self._startup_drop_frames = 4

    def start(self) -> bool:
        self._stopping = False
        return self._open_stream_session(request_stream=True, reason="startup")

    def read(self) -> tuple[bool, Any]:
        if self._stopping:
            return False, None

        cap = self.cap
        if cap is None:
            self._maybe_restart("capture_missing")
            return False, None

        ok, frame = self._read_frame_once(cap)
        if ok:
            self._failed_reads = 0
            if not self._live:
                self._live = True
                if not self._logged_first_frame:
                    self._logged_first_frame = True
                    log("[VIDEO]", "First valid Tello frame received", url=self.video_url)
            return True, frame

        self._failed_reads += 1
        if self._should_log_status():
            log(
                "[VIDEO]",
                "No valid frames yet",
                source="tello",
                failed_reads=self._failed_reads,
            )

        if self._failed_reads >= self.stall_reads:
            self.restart_stream(reason="stalled")

        return False, None

    def restart_stream(self, reason: str = "restart") -> bool:
        if self._stopping:
            return False

        now = time.monotonic()
        if now - self._last_restart_ts < self._restart_backoff_s:
            return False

        if not self._restart_lock.acquire(blocking=False):
            return False

        try:
            self._last_restart_ts = now
            log("[VIDEO]", "Reconnect scheduled", reason=reason, delay_s=self._restart_backoff_s)
            if not self._sleep_with_stop(self._restart_backoff_s):
                return False
            log("[VIDEO]", "Reopening Tello capture", reason=reason)
            return self._open_stream_session(request_stream=False, reason=reason)
        finally:
            self._restart_lock.release()

    def release(self) -> None:
        self._stopping = True
        self._release_capture(reason="shutdown")
        self._disable_stream(reason="shutdown")

    def _open_stream_session(self, request_stream: bool, reason: str) -> bool:
        self._mark_not_live()
        self._release_capture(reason=f"{reason}_reopen")

        if self.drone.enabled and not self.drone.is_sdk_mode_enabled():
            log("[VIDEO]", "Skipping video connect before SDK mode", reason=reason, sdk_mode=False)
            return False

        if self.drone.enabled and (request_stream or not self._stream_enabled) and not self._ensure_stream_on(reason=reason):
            return False

        if self.warmup_s > 0:
            log("[VIDEO]", "Stabilizing stream before capture reads", reason=reason, delay_s=self.warmup_s)
            if not self._sleep_with_stop(self.warmup_s):
                return False

        for attempt in range(1, self._startup_open_attempts + 1):
            cap, opened_url, backend_name = self._open_capture()
            if cap is None:
                continue

            self._capture_open_attempts += 1
            self.cap = cap
            log(
                "[VIDEO]",
                "Stream open success",
                attempt=attempt,
                backend=backend_name,
                url=opened_url,
                session_attempt=self._capture_open_attempts,
            )

            self._drop_initial_frames(cap, reason=reason)
            frame = self._await_first_frame(cap)
            if frame is not None:
                self._live = True
                self._logged_first_frame = True
                self._failed_reads = 0
                self._reconnect_failures = 0
                log("[VIDEO]", "First valid Tello frame received", url=self.video_url)
                return True

            log(
                "[VIDEO]",
                "Stream open produced no valid frames",
                attempt=attempt,
                source="tello",
            )
            self._release_capture(reason="open_failed")

            if attempt < self._startup_open_attempts and not self._sleep_with_stop(0.35):
                return False

        self._reconnect_failures += 1
        if self.drone.enabled and self._stream_enabled and self._reconnect_failures >= 2:
            self._reset_stream(reason=f"{reason}_recovery")
        log("[VIDEO]", "Unable to acquire Tello frames", source="tello", reason=reason)
        return False

    def _open_capture(self) -> tuple[cv2.VideoCapture | None, str | None, str | None]:
        log("[VIDEO]", "Video connect attempt", url=self.video_url)
        for url in self._capture_urls():
            for backend in (cv2.CAP_FFMPEG, None):
                cap = None
                try:
                    cap = cv2.VideoCapture(url, backend) if backend is not None else cv2.VideoCapture(url)
                    if not cap.isOpened():
                        self._safe_release_cap(cap)
                        continue

                    self._configure_capture(cap)
                    backend_name = "ffmpeg" if backend == cv2.CAP_FFMPEG else "default"
                    return cap, url, backend_name
                except cv2.error as exc:
                    log("[VIDEO]", "Stream open failure", url=url, backend=backend, error=exc)
                    self._safe_release_cap(cap)
                    continue
                except OSError as exc:
                    log("[VIDEO]", "Stream open failure", url=url, backend=backend, error=exc)
                    self._safe_release_cap(cap)
                    continue

        log("[VIDEO]", "Stream open failure", url=self.video_url)
        return None, None, None

    def _capture_urls(self) -> list[str]:
        base_url = self.video_url
        if not base_url.lower().startswith("udp://"):
            return [base_url]

        params = {
            "fifo_size": "5000000",
            "overrun_nonfatal": "1",
            "buffer_size": "65535",
            "fflags": "nobuffer",
            "flags": "low_delay",
            "max_delay": "0",
        }
        separator = "&" if "?" in base_url else "?"
        tuned_url = f"{base_url}{separator}{urlencode(params)}"

        if tuned_url == base_url:
            return [base_url]
        return [tuned_url, base_url]

    def _configure_capture(self, cap: cv2.VideoCapture) -> None:
        for prop_name, value in (
            ("CAP_PROP_BUFFERSIZE", 1),
            ("CAP_PROP_OPEN_TIMEOUT_MSEC", 2500),
            ("CAP_PROP_READ_TIMEOUT_MSEC", 1000),
        ):
            prop = getattr(cv2, prop_name, None)
            if prop is None:
                continue
            try:
                cap.set(prop, value)
            except cv2.error:
                continue

    def _drop_initial_frames(self, cap: cv2.VideoCapture, *, reason: str) -> None:
        if self._startup_drop_frames <= 0:
            return
        log("[VIDEO]", "Dropping initial frames", reason=reason, frames=self._startup_drop_frames)
        for _ in range(self._startup_drop_frames):
            if self._stopping:
                return
            try:
                if not cap.grab():
                    break
            except cv2.error:
                break

    def _await_first_frame(self, cap: cv2.VideoCapture) -> Any:
        for attempt in range(1, self._first_frame_attempts + 1):
            ok, frame = self._read_frame_once(cap)
            if ok:
                return frame

            if attempt in (1, 10, 20, self._first_frame_attempts):
                log(
                    "[VIDEO]",
                    "Waiting for first valid Tello frame",
                    attempt=attempt,
                    max_attempts=self._first_frame_attempts,
                )
            time.sleep(self._first_frame_delay_s)

        return None

    def _read_frame_once(self, cap: cv2.VideoCapture) -> tuple[bool, Any]:
        try:
            ok, frame = cap.read()
        except cv2.error as exc:
            if self._should_log_status():
                log("[VIDEO]", "OpenCV read failed", url=self.video_url, error=exc)
            return False, None
        except OSError as exc:
            if self._should_log_status():
                log("[VIDEO]", "Video read failed", url=self.video_url, error=exc)
            return False, None

        if not ok or frame is None:
            return False, None

        shape = getattr(frame, "shape", None)
        if not shape or len(shape) < 2 or shape[0] <= 0 or shape[1] <= 0:
            return False, None

        return True, frame

    def _maybe_restart(self, reason: str) -> None:
        now = time.monotonic()
        if now - self._last_restart_ts < self._restart_backoff_s:
            return
        self.restart_stream(reason=reason)

    def _mark_not_live(self) -> None:
        self._live = False
        self._logged_first_frame = False
        self._failed_reads = 0

    def _release_capture(self, *, reason: str) -> None:
        cap = self.cap
        self.cap = None
        self._mark_not_live()
        if cap is not None:
            log("[VIDEO]", "Capture released", reason=reason, url=self.video_url)
        self._safe_release_cap(cap)

    def _safe_release_cap(self, cap: cv2.VideoCapture | None) -> None:
        if cap is None:
            return
        try:
            cap.release()
        except cv2.error:
            pass

    def _ensure_stream_on(self, *, reason: str) -> bool:
        if self._stream_enabled:
            log("[VIDEO]", "Skipping duplicate stream request", reason=reason, streamon_ok=True)
            return True
        log("[VIDEO]", "Requesting Tello stream", reason=reason)
        if not self.drone.send_command("streamon"):
            log("[VIDEO]", "Tello stream request failed", reason=reason, streamon_ok=False)
            return False
        self._stream_enabled = True
        log("[VIDEO]", "Tello stream enabled", reason=reason, streamon_ok=True)
        return True

    def _disable_stream(self, *, reason: str) -> None:
        if not self.drone.enabled or not self._stream_enabled:
            self._stream_enabled = False
            return
        if not self.drone.is_sdk_mode_enabled():
            self._stream_enabled = False
            return
        if self.drone.send_command("streamoff"):
            log("[VIDEO]", "Tello stream disabled", reason=reason, streamoff_ok=True)
        else:
            log("[VIDEO]", "Tello stream disable failed", reason=reason, streamoff_ok=False)
        self._stream_enabled = False

    def _reset_stream(self, *, reason: str) -> None:
        log("[VIDEO]", "Resetting Tello stream", reason=reason, reconnect_failures=self._reconnect_failures)
        self._disable_stream(reason=reason)
        if not self._sleep_with_stop(0.25):
            return
        self._ensure_stream_on(reason=reason)

    def _sleep_with_stop(self, delay_s: float) -> bool:
        remaining = max(0.0, delay_s)
        while not self._stopping and remaining > 0:
            step = min(0.05, remaining)
            time.sleep(step)
            remaining -= step
        return not self._stopping

    def _should_log_status(self) -> bool:
        now = time.monotonic()
        if now - self._last_no_frame_log < self._status_log_interval_s:
            return False
        self._last_no_frame_log = now
        return True
