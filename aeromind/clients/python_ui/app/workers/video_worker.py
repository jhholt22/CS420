from __future__ import annotations

import time
from threading import Lock
from time import monotonic
from typing import Any, Callable

import cv2
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage, QPixmap

from app.models.video_source import VideoSourceSpec
from app.services.video_stream_service import VideoStreamService
from app.utils.logging_utils import gesture_debug_log


class VideoWorker(QObject):
    frameReady = Signal(QPixmap)
    rawFrameReady = Signal(object)
    streamStatusChanged = Signal(str)
    workerStarted = Signal()
    workerFinished = Signal()

    def __init__(
        self,
        video_service: VideoStreamService,
        initial_source: VideoSourceSpec,
        reconnect_delay_ms: int,
        *,
        read_interval_ms: int = 30,
        drop_frames_on_reconnect: int = 3,
        inference_emit_interval_ms: int = 100,
        perf_log_interval_ms: int = 5000,
        frame_sink: Callable[[Any], None] | None = None,
    ) -> None:
        super().__init__()
        self.video_service = video_service
        self._source = initial_source
        self._pending_source: VideoSourceSpec | None = None
        self._source_lock = Lock()
        self.reconnect_delay_ms = reconnect_delay_ms if reconnect_delay_ms > 0 else 1000
        self.read_interval_ms = read_interval_ms if read_interval_ms > 0 else 30
        self.drop_frames_on_reconnect = max(0, drop_frames_on_reconnect)
        self.inference_emit_interval_ms = inference_emit_interval_ms if inference_emit_interval_ms > 0 else 100
        self.perf_log_interval_ms = perf_log_interval_ms if perf_log_interval_ms > 0 else 5000
        self.frame_sink = frame_sink
        self._running = False
        self._last_status: str | None = None
        self._logged_first_good_frame = False
        self._last_inference_emit_at = 0.0
        self._read_frames_since_log = 0
        self._perf_window_started_at = monotonic()

    def start(self) -> None:
        if self._running:
            gesture_debug_log("thread.worker_start_skipped", worker="video", reason="already_running")
            return

        self._running = True
        gesture_debug_log("thread.worker_started", worker="video")
        self.workerStarted.emit()
        self._emit_status("Connecting")

        try:
            while self._running:
                self._apply_pending_source_if_needed()
                if not self._open_stream():
                    self._handle_stream_failure()
                    continue

                self._logged_first_good_frame = False
                self._last_inference_emit_at = 0.0
                self._read_frames_since_log = 0
                self._perf_window_started_at = monotonic()
                self._drop_initial_frames()
                if not self._running:
                    break
                self._emit_status("Live")

                if not self._read_stream_loop():
                    self._handle_stream_failure()
        finally:
            self.video_service.close()
            self._emit_status("Stopped")
            self._running = False
            gesture_debug_log("thread.worker_finished", worker="video")
            self.workerFinished.emit()

    def stop(self) -> None:
        gesture_debug_log("thread.worker_stop_requested", worker="video", running=self._running)
        if not self._running:
            self.video_service.close()
            self._emit_status("Stopped")
            return

        self._running = False
        self.video_service.close()
        self._emit_status("Stopped")

    def set_source(self, source: VideoSourceSpec, *, mode: str | None = None, reason: str = "manual") -> None:
        with self._source_lock:
            current = self._pending_source or self._source
            if current == source:
                return
            self._pending_source = source
        gesture_debug_log(
            "video.source_selected",
            mode=(mode or "--").lower(),
            reason=reason,
            source_kind=source.kind,
            source_value=source.value,
            source_label=source.label,
        )

    def _open_stream(self) -> bool:
        try:
            return self.video_service.open_stream(self._source)
        except cv2.error as exc:
            gesture_debug_log("thread.worker_error", worker="video", stage="open_stream", error=repr(exc))
            self.video_service.close()
            return False
        except RuntimeError as exc:
            gesture_debug_log("thread.worker_error", worker="video", stage="open_stream", error=repr(exc))
            self.video_service.close()
            return False

    def _drop_initial_frames(self) -> None:
        for _ in range(self.drop_frames_on_reconnect):
            if not self._running:
                return
            if not self.video_service.grab():
                break

    def _read_stream_loop(self) -> bool:
        while self._running:
            if self._has_pending_source_change():
                return False
            frame = self.video_service.read_frame()
            if not self._running:
                return True
            if frame is None:
                return False

            # Timestamp as close as possible to the successful capture/read boundary.
            frame_captured_at = monotonic()

            if not self._logged_first_good_frame:
                self._logged_first_good_frame = True
                event_name = "video.webcam_first_frame" if self._source.kind == "webcam" else "video.first_good_frame"
                gesture_debug_log(
                    event_name,
                    source_kind=self._source.kind,
                    source_value=self._source.value,
                    source_label=self._source.label,
                )

            self._read_frames_since_log += 1
            self._emit_performance_log_if_due()

            if self._should_emit_inference_frame():
                inference_frame = frame.copy()
                try:
                    if self.frame_sink is not None:
                        self.frame_sink(inference_frame, frame_captured_at=frame_captured_at)
                    else:
                        self.rawFrameReady.emit(inference_frame)
                except Exception as exc:
                    gesture_debug_log(
                        "thread.worker_error",
                        worker="video",
                        stage="frame_sink",
                        error=f"{type(exc).__name__}: {exc}",
                    )

            if not self._running:
                return True

            pixmap = self._frame_to_pixmap(frame)
            if not self._running:
                return True
            if not pixmap.isNull():
                self.frameReady.emit(pixmap)

            if not self._sleep_ms(self.read_interval_ms):
                return True
        return True

    def _handle_stream_failure(self) -> None:
        self.video_service.close()
        if not self._running:
            return
        if self._has_pending_source_change():
            self._apply_pending_source_if_needed()
            self._emit_status("Connecting")
            return
        self._emit_status("Reconnecting")
        gesture_debug_log(
            "video.reconnect_scheduled",
            source_kind=self._source.kind,
            source_value=self._source.value,
            delay_ms=self.reconnect_delay_ms,
        )
        self._sleep_ms(self.reconnect_delay_ms)
        if self._running:
            self._emit_status("Connecting")

    def _frame_to_pixmap(self, frame: Any) -> QPixmap:
        try:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            height, width, channels = rgb_frame.shape
            bytes_per_line = channels * width
            image = QImage(
                rgb_frame.data,
                width,
                height,
                bytes_per_line,
                QImage.Format_RGB888,
            ).copy()
            return QPixmap.fromImage(image)
        except (cv2.error, RuntimeError, ValueError):
            return QPixmap()

    def _emit_status(self, text: str) -> None:
        if text != self._last_status:
            self._last_status = text
            self.streamStatusChanged.emit(text)

    def _sleep_ms(self, delay_ms: int) -> bool:
        remaining = max(0.0, delay_ms / 1000.0)
        while self._running and remaining > 0:
            if self._has_pending_source_change():
                return self._running
            step = min(0.05, remaining)
            time.sleep(step)
            remaining -= step
        return self._running

    def _has_pending_source_change(self) -> bool:
        with self._source_lock:
            return self._pending_source is not None

    def _apply_pending_source_if_needed(self) -> None:
        with self._source_lock:
            pending = self._pending_source
            self._pending_source = None
        if pending is None or pending == self._source:
            return
        self._source = pending
        self._logged_first_good_frame = False
        self._last_inference_emit_at = 0.0
        self._read_frames_since_log = 0
        self._perf_window_started_at = monotonic()
        self.video_service.close()
        self._emit_status("Connecting")

    def _should_emit_inference_frame(self) -> bool:
        now = monotonic()
        elapsed_ms = (now - self._last_inference_emit_at) * 1000.0
        if self._last_inference_emit_at <= 0.0 or elapsed_ms >= self.inference_emit_interval_ms:
            self._last_inference_emit_at = now
            return True
        return False

    def _emit_performance_log_if_due(self) -> None:
        now = monotonic()
        elapsed_ms = (now - self._perf_window_started_at) * 1000.0
        if elapsed_ms < self.perf_log_interval_ms:
            return
        fps = self._read_frames_since_log / max(0.001, elapsed_ms / 1000.0)
        gesture_debug_log(
            "performance.video_read",
            source_kind=self._source.kind,
            source_value=self._source.value,
            frame_read_fps=f"{fps:.2f}",
            interval_ms=int(elapsed_ms),
        )
        self._read_frames_since_log = 0
        self._perf_window_started_at = now
