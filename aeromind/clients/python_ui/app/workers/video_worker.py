from __future__ import annotations

import time
from typing import Any

import cv2
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage, QPixmap

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
        stream_url: str,
        reconnect_delay_ms: int,
        *,
        read_interval_ms: int = 30,
        drop_frames_on_reconnect: int = 3,
    ) -> None:
        super().__init__()
        self.video_service = video_service
        self.stream_url = stream_url
        self.reconnect_delay_ms = reconnect_delay_ms if reconnect_delay_ms > 0 else 1000
        self.read_interval_ms = read_interval_ms if read_interval_ms > 0 else 30
        self.drop_frames_on_reconnect = max(0, drop_frames_on_reconnect)
        self._running = False
        self._last_status: str | None = None

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
                if not self._open_stream():
                    self._handle_stream_failure()
                    continue

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

    def _open_stream(self) -> bool:
        try:
            return self.video_service.open_stream(self.stream_url)
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
            frame = self.video_service.read_frame()
            if not self._running:
                return True
            if frame is None:
                return False

            self.rawFrameReady.emit(frame.copy())

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
        self._emit_status("Reconnecting")
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
            step = min(0.05, remaining)
            time.sleep(step)
            remaining -= step
        return self._running
