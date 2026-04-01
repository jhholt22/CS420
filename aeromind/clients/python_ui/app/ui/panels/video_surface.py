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
        self._has_video = False

        palette = self.palette()
        palette.setColor(QPalette.Window, QColor("#020617"))
        self.setPalette(palette)

        self.video_label = QLabel("NO LIVE FEED", self)
        self.video_label.setObjectName("videoSurfaceLabel")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setScaledContents(False)

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
        self.reticle_overlay.setGeometry(self.rect())
        self.overlay_container.setGeometry(self.rect())
        self.stream_status_label.setGeometry(self.width() - 138, 18, 118, 28)

    def set_video_pixmap(self, pixmap: QPixmap) -> None:
        if pixmap.isNull():
            self._has_video = False
            self.video_label.setPixmap(QPixmap())
            self.video_label.setText("NO LIVE FEED")
            self.reticle_overlay.show()
            return

        self._has_video = True
        scaled = pixmap.scaled(
            self.video_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.video_label.setPixmap(scaled)
        self.video_label.setText("")
        self.reticle_overlay.hide()

    def set_stream_status(self, text: str) -> None:
        status_text = text.upper() if text else "NO SIGNAL"
        self.stream_status_label.setText(status_text)
        if text != "Live" and not self._has_video:
            self.video_label.setText("NO LIVE FEED")
            self.reticle_overlay.show()
