from __future__ import annotations

import cv2
from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtGui import QImage, QPixmap

from app.services.video_stream_service import VideoStreamService


class VideoWorker(QObject):
    frameReady = Signal(QPixmap)
    streamStatusChanged = Signal(str)

    def __init__(
        self,
        video_service: VideoStreamService,
        video_url: str,
        reconnect_delay_ms: int,
    ) -> None:
        super().__init__()
        self.video_service = video_service
        self.video_url = video_url
        self.reconnect_delay_ms = reconnect_delay_ms
        self._running = False

    def start(self) -> None:
        self._running = True
        self.streamStatusChanged.emit("No Signal")

        while self._running:
            if not self.video_service.open_stream(self.video_url):
                self.streamStatusChanged.emit("Reconnecting...")
                QThread.msleep(self.reconnect_delay_ms)
                continue

            self.streamStatusChanged.emit("Live")

            while self._running:
                frame = self.video_service.read_frame()
                if frame is None:
                    self.streamStatusChanged.emit("Reconnecting...")
                    self.video_service.close()
                    QThread.msleep(self.reconnect_delay_ms)
                    break

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
                self.frameReady.emit(QPixmap.fromImage(image))
                QThread.msleep(30)

        self.video_service.close()
        self.streamStatusChanged.emit("No Signal")

    def stop(self) -> None:
        self._running = False
