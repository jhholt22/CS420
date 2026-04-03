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

        self._cap: cv2.VideoCapture | None = None
        self._worker_thread: threading.Thread | None = None
        self._worker_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._frame_lock = threading.Lock()
        self._restart_lock = threading.Lock()
        self._startup_event = threading.Event()
        self._stop_event = threading.Event()
        self._restart_requested = False
        self._restart_reason = "restart"
        self._state = "disconnected"

        self._failed_reads = 0
        self._logged_first_frame = False
        self._live = False
        self._last_no_frame_log = 0.0
        self._last_restart_ts = 0.0
        self._stream_enabled = False
        self._reconnect_failures = 0
        self._capture_open_attempts = 0

        self._latest_frame: Any = None
        self._latest_frame_seq = 0
        self._last_consumed_frame_seq = 0

        self._startup_open_attempts = 3
        self._first_frame_attempts = 30
        self._first_frame_delay_s = 0.10
        self._restart_backoff_s = max(0.75, watchdog_s / 2.0)
        self._status_log_interval_s = 2.0
        self._startup_drop_frames = 4
        self._startup_wait_timeout_s = max(2.0, self.warmup_s + (self._startup_open_attempts * self._first_frame_attempts * self._first_frame_delay_s))

    def start(self) -> bool:
        with self._worker_lock:
            self._stop_event.clear()
            self._startup_event.clear()
            self._restart_requested = False
            self._restart_reason = "startup"
            if self._worker_thread is None or not self._worker_thread.is_alive():
                self._worker_thread = threading.Thread(
                    target=self._worker_loop,
                    name="tello-video-worker",
                    daemon=True,
                )
                self._worker_thread.start()
        started = self._startup_event.wait(timeout=self._startup_wait_timeout_s)
        return started and self.is_live()

    def read(self) -> tuple[bool, Any]:
        with self._frame_lock:
            if self._latest_frame is None or self._latest_frame_seq == self._last_consumed_frame_seq:
                return False, None
            frame = self._latest_frame.copy()
            self._last_consumed_frame_seq = self._latest_frame_seq
        return True, frame

    def restart_stream(self, reason: str = "restart") -> bool:
        if self._stop_event.is_set():
            return False
        now = time.monotonic()
        if now - self._last_restart_ts < self._restart_backoff_s:
            return False
        with self._restart_lock:
            self._restart_requested = True
            self._restart_reason = reason
            self._last_restart_ts = now
        self._log_lifecycle("Restart requested", reason=reason)
        return True

    def release(self) -> None:
        self._stop_event.set()
        self._startup_event.set()
        thread = self._worker_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=3.0)
        self._worker_thread = None

    def is_live(self) -> bool:
        with self._state_lock:
            return self._live

    def _worker_loop(self) -> None:
        self._set_state("connecting")
        try:
            request_stream = True
            reason = "startup"
            while not self._stop_event.is_set():
                if not self._open_stream_session(request_stream=request_stream, reason=reason):
                    if self._stop_event.is_set():
                        break
                    request_stream = False
                    reason = self._consume_restart_reason(default="reconnect")
                    self._set_state("restarting")
                    if not self._sleep_with_stop(self._restart_backoff_s):
                        break
                    self._set_state("connecting")
                    continue

                self._startup_event.set()
                self._set_state("streaming")
                request_stream = False

                while not self._stop_event.is_set():
                    cap = self._cap
                    if cap is None:
                        break
                    ok, frame = self._read_frame_once(cap)
                    if ok:
                        self._failed_reads = 0
                        if not self._live:
                            self._live = True
                            if not self._logged_first_frame:
                                self._logged_first_frame = True
                                self._log_lifecycle("First valid Tello frame received", url=self.video_url)
                        self._publish_frame(frame)
                    else:
                        self._failed_reads += 1
                        if self._should_log_status():
                            self._log_lifecycle(
                                "No valid frames yet",
                                source="tello",
                                failed_reads=self._failed_reads,
                            )
                        if self._failed_reads >= self.stall_reads:
                            self.restart_stream(reason="stalled")

                    if self._consume_restart_request():
                        restart_reason = self._consume_restart_reason(default="restart")
                        self._log_lifecycle("Restart executed by worker", reason=restart_reason)
                        self._set_state("restarting")
                        self._release_capture(reason=f"{restart_reason}_reopen")
                        reason = restart_reason
                        break
                else:
                    reason = "stopped"

                if self._stop_event.is_set():
                    break
                if self._cap is None:
                    request_stream = False
                    if not self._sleep_with_stop(self._restart_backoff_s):
                        break
                    self._set_state("connecting")
                    continue
        finally:
            self._set_state("stopping")
            self._release_capture(reason="shutdown")
            self._disable_stream(reason="shutdown")
            self._set_state("disconnected")
            self._startup_event.set()

    def _open_stream_session(self, request_stream: bool, reason: str) -> bool:
        self._mark_not_live()
        self._release_capture(reason=f"{reason}_reopen")

        if self.drone.enabled and not self.drone.is_sdk_mode_enabled():
            self._log_lifecycle("Skipping video connect before SDK mode", reason=reason, sdk_mode=False)
            return False

        if self.drone.enabled and (request_stream or not self._stream_enabled) and not self._ensure_stream_on(reason=reason):
            return False

        if self.warmup_s > 0:
            self._log_lifecycle("Stabilizing stream before capture reads", reason=reason, delay_s=self.warmup_s)
            if not self._sleep_with_stop(self.warmup_s):
                return False

        for attempt in range(1, self._startup_open_attempts + 1):
            cap, opened_url, backend_name = self._open_capture()
            if cap is None:
                continue

            self._capture_open_attempts += 1
            self._cap = cap
            self._log_lifecycle(
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
                self._publish_frame(frame)
                return True

            self._log_lifecycle(
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
        self._log_lifecycle("Unable to acquire Tello frames", source="tello", reason=reason)
        return False

    def _open_capture(self) -> tuple[cv2.VideoCapture | None, str | None, str | None]:
        self._log_lifecycle("Capture open start", url=self.video_url)
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
                    self._log_lifecycle("Capture open success", url=url, backend=backend_name)
                    return cap, url, backend_name
                except cv2.error as exc:
                    self._log_lifecycle("Capture open failure", url=url, backend=backend, error=exc)
                    self._safe_release_cap(cap)
                    continue
                except Exception as exc:
                    self._log_lifecycle("Capture open failure", url=url, backend=backend, error=exc)
                    self._safe_release_cap(cap)
                    continue

        self._log_lifecycle("Capture open failure", url=self.video_url)
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
        self._log_lifecycle("Dropping initial frames", reason=reason, frames=self._startup_drop_frames)
        for _ in range(self._startup_drop_frames):
            if self._stop_event.is_set():
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
                self._log_lifecycle(
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
                self._log_lifecycle("OpenCV read failed", url=self.video_url, error=exc)
            return False, None
        except Exception as exc:
            if self._should_log_status():
                self._log_lifecycle("OpenCV read failed", url=self.video_url, error=exc)
            return False, None

        if not ok or frame is None:
            return False, None

        shape = getattr(frame, "shape", None)
        if not shape or len(shape) < 2 or shape[0] <= 0 or shape[1] <= 0:
            return False, None

        return True, frame

    def _publish_frame(self, frame: Any) -> None:
        with self._frame_lock:
            self._latest_frame = frame
            self._latest_frame_seq += 1

    def _mark_not_live(self) -> None:
        self._live = False
        self._logged_first_frame = False
        self._failed_reads = 0

    def _release_capture(self, *, reason: str) -> None:
        cap = self._cap
        self._cap = None
        self._mark_not_live()
        if cap is None:
            return
        self._log_lifecycle("Capture release start", reason=reason, url=self.video_url)
        self._safe_release_cap(cap)
        self._log_lifecycle("Capture release done", reason=reason, url=self.video_url)

    def _safe_release_cap(self, cap: cv2.VideoCapture | None) -> None:
        if cap is None:
            return
        try:
            cap.release()
        except cv2.error as exc:
            self._log_lifecycle("Capture release failure", error=exc)

    def _ensure_stream_on(self, *, reason: str) -> bool:
        if self._stream_enabled:
            self._log_lifecycle("Skipping duplicate stream request", reason=reason, streamon_ok=True)
            return True
        self._log_lifecycle("Requesting Tello stream", reason=reason)
        if not self.drone.send_command("streamon"):
            self._log_lifecycle("Tello stream request failed", reason=reason, streamon_ok=False)
            return False
        self._stream_enabled = True
        self._log_lifecycle("Tello stream enabled", reason=reason, streamon_ok=True)
        return True

    def _disable_stream(self, *, reason: str) -> None:
        if not self.drone.enabled or not self._stream_enabled:
            self._stream_enabled = False
            return
        if not self.drone.is_sdk_mode_enabled():
            self._stream_enabled = False
            return
        if self.drone.send_command("streamoff"):
            self._log_lifecycle("Tello stream disabled", reason=reason, streamoff_ok=True)
        else:
            self._log_lifecycle("Tello stream disable failed", reason=reason, streamoff_ok=False)
        self._stream_enabled = False

    def _reset_stream(self, *, reason: str) -> None:
        self._log_lifecycle("Resetting Tello stream", reason=reason, reconnect_failures=self._reconnect_failures)
        self._disable_stream(reason=reason)
        if not self._sleep_with_stop(0.25):
            return
        self._ensure_stream_on(reason=reason)

    def _sleep_with_stop(self, delay_s: float) -> bool:
        remaining = max(0.0, delay_s)
        while not self._stop_event.is_set() and remaining > 0:
            step = min(0.05, remaining)
            time.sleep(step)
            remaining -= step
        return not self._stop_event.is_set()

    def _should_log_status(self) -> bool:
        now = time.monotonic()
        if now - self._last_no_frame_log < self._status_log_interval_s:
            return False
        self._last_no_frame_log = now
        return True

    def _consume_restart_request(self) -> bool:
        with self._restart_lock:
            return self._restart_requested

    def _consume_restart_reason(self, *, default: str) -> str:
        with self._restart_lock:
            reason = self._restart_reason or default
            self._restart_requested = False
            self._restart_reason = default
            return reason

    def _set_state(self, state: str) -> None:
        with self._state_lock:
            if self._state == state:
                return
            previous = self._state
            self._state = state
        self._log_lifecycle("State changed", previous=previous, state=state)

    @staticmethod
    def _thread_name() -> str:
        return threading.current_thread().name

    def _log_lifecycle(self, component: str, **fields: Any) -> None:
        log("[VIDEO]", component, thread=self._thread_name(), **fields)
