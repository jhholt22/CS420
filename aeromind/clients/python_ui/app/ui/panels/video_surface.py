from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QWidget


class _ReticleOverlay(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        center = self.rect().center()
        painter.setPen(QPen(QColor(125, 211, 252, 28), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(center, 56, 56)
        painter.drawEllipse(center, 104, 104)

        painter.setPen(QPen(QColor(148, 163, 184, 34), 1))
        painter.drawLine(center.x() - 160, center.y(), center.x() - 84, center.y())
        painter.drawLine(center.x() + 84, center.y(), center.x() + 160, center.y())
        painter.drawLine(center.x(), center.y() - 160, center.x(), center.y() - 84)
        painter.drawLine(center.x(), center.y() + 84, center.x(), center.y() + 160)

        frame_color = QColor(148, 163, 184, 24)
        painter.setPen(QPen(frame_color, 1))
        inset = 28
        arm = 48
        painter.drawLine(inset, inset, inset + arm, inset)
        painter.drawLine(inset, inset, inset, inset + arm)
        painter.drawLine(self.width() - inset - arm, inset, self.width() - inset, inset)
        painter.drawLine(self.width() - inset, inset, self.width() - inset, inset + arm)
        painter.drawLine(inset, self.height() - inset, inset + arm, self.height() - inset)
        painter.drawLine(inset, self.height() - inset - arm, inset, self.height() - inset)
        painter.drawLine(self.width() - inset - arm, self.height() - inset, self.width() - inset, self.height() - inset)
        painter.drawLine(self.width() - inset, self.height() - inset - arm, self.width() - inset, self.height() - inset)


class VideoSurface(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("videoSurface")
        self.setAutoFillBackground(True)
        self._is_live = False
        self._current_status = "No Signal"

        palette = self.palette()
        palette.setColor(QPalette.Window, QColor("#020617"))
        self.setPalette(palette)

        self.video_label = QLabel("", self)
        self.video_label.setObjectName("videoSurfaceLabel")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setScaledContents(False)

        self.placeholder_label = QLabel("NO DRONE FEED", self)
        self.placeholder_label.setObjectName("videoSurfaceLabel")
        self.placeholder_label.setAlignment(Qt.AlignCenter)

        self.placeholder_subtext = QLabel("Waiting for MJPEG stream", self)
        self.placeholder_subtext.setObjectName("videoSurfaceSubtext")
        self.placeholder_subtext.setAlignment(Qt.AlignCenter)

        self.reticle_overlay = _ReticleOverlay(self)
        self.reticle_overlay.raise_()

        self.overlay_container = QWidget(self)
        self.overlay_container.setObjectName("videoOverlayContainer")
        self.overlay_container.raise_()

        self.stream_status_label = QLabel("NO SIGNAL", self.overlay_container)
        self.stream_status_label.setObjectName("videoStatusBadge")
        self.stream_status_label.setAlignment(Qt.AlignCenter)
        self.stream_status_label.raise_()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.video_label.setGeometry(self.rect())
        self.placeholder_label.setGeometry(0, max(0, self.height() // 2 - 26), self.width(), 24)
        self.placeholder_subtext.setGeometry(0, max(0, self.height() // 2 + 2), self.width(), 18)
        self.reticle_overlay.setGeometry(self.rect())
        self.overlay_container.setGeometry(self.rect())
        self.stream_status_label.setGeometry(self.width() - 138, 18, 118, 28)

    def set_video_pixmap(self, pixmap: QPixmap) -> None:
        if pixmap.isNull():
            self.video_label.setPixmap(QPixmap())
            self.set_stream_live(False)
            return

        scaled = pixmap.scaled(
            self.video_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.video_label.setPixmap(scaled)
        self.set_stream_live(True)

    def set_stream_status(self, text: str) -> None:
        self._current_status = text.strip() if text else "No Signal"
        status_text = self._current_status.upper()
        self.stream_status_label.setText(status_text)

        if self._current_status == "Live":
            self.set_stream_live(True)
            return

        self.set_stream_live(False)

        if self._current_status == "Connecting":
            self.placeholder_label.setText("CONNECTING TO DRONE FEED")
            self.placeholder_subtext.setText("Opening MJPEG stream")
        elif self._current_status == "Reconnecting":
            self.placeholder_label.setText("RECONNECTING")
            self.placeholder_subtext.setText("Restoring MJPEG stream")
        elif self._current_status == "Stopped":
            self.placeholder_label.setText("FEED STOPPED")
            self.placeholder_subtext.setText("Video worker stopped")
        else:
            self.placeholder_label.setText("NO DRONE FEED")
            self.placeholder_subtext.setText("Waiting for MJPEG stream")

    def set_stream_live(self, is_live: bool) -> None:
        self._is_live = is_live
        has_pixmap = self.video_label.pixmap() is not None and not self.video_label.pixmap().isNull()

        if is_live and has_pixmap:
            self.placeholder_label.hide()
            self.placeholder_subtext.hide()
            self.reticle_overlay.hide()
            return

        self.video_label.setPixmap(QPixmap())
        self.placeholder_label.show()
        self.placeholder_subtext.show()
        self.reticle_overlay.show()
