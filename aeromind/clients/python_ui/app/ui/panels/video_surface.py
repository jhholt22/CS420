from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette, QPixmap
from PySide6.QtWidgets import QLabel, QWidget


class VideoSurface(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("videoSurface")
        self.setAutoFillBackground(True)

        palette = self.palette()
        palette.setColor(QPalette.Window, QColor("#020617"))
        self.setPalette(palette)

        self.video_label = QLabel("Waiting for video...", self)
        self.video_label.setObjectName("videoSurfaceLabel")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setScaledContents(False)

        self.overlay_container = QWidget(self)
        self.overlay_container.setObjectName("videoOverlayContainer")
        self.overlay_container.raise_()

        self.stream_status_label = QLabel("No Signal", self.overlay_container)
        self.stream_status_label.setObjectName("videoStatusBadge")
        self.stream_status_label.setAlignment(Qt.AlignCenter)
        self.stream_status_label.raise_()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.video_label.setGeometry(self.rect())
        self.overlay_container.setGeometry(self.rect())
        self.stream_status_label.setGeometry(self.width() - 144, 24, 120, 32)

    def set_video_pixmap(self, pixmap: QPixmap) -> None:
        if pixmap.isNull():
            self.video_label.setText("Waiting for video...")
            self.video_label.setPixmap(QPixmap())
            return

        scaled = pixmap.scaled(
            self.video_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.video_label.setPixmap(scaled)
        self.video_label.setText("")

    def set_stream_status(self, text: str) -> None:
        self.stream_status_label.setText(text)
        if text != "Live" and self.video_label.pixmap() is None:
            self.video_label.setText("Waiting for video...")
