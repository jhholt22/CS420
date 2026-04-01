from __future__ import annotations

from PySide6.QtWidgets import QWidget


class VideoOverlay(QWidget):
    """Transparent overlay container for HUD elements on top of the video feed."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("videoOverlayContainer")
        self.setAttribute(self.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("QWidget#videoOverlayContainer { background: transparent; }")
