from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class GestureDebugPanel(QWidget):
    gestureToggleClicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("gestureDebugPanel")
        self.setAttribute(Qt.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        self.gesture_toggle_button = QPushButton("GESTURE OFF", self)
        self.gesture_toggle_button.setObjectName("gestureToggleButton")
        self.gesture_toggle_button.setProperty("state", "off")
        self.gesture_toggle_button.clicked.connect(self.gestureToggleClicked)
        layout.addWidget(self.gesture_toggle_button)

        self.gesture_label = QLabel("Gesture: OFF", self)
        self.detector_label = QLabel("Detector: OFFLINE", self)
        self.raw_label = QLabel("Raw: --", self)
        self.stable_label = QLabel("Stable: --", self)
        self.confidence_label = QLabel("Confidence: --", self)
        self.last_command_label = QLabel("Last Command: --", self)
        self.queue_label = QLabel("Queue: idle", self)

        for widget in (
            self.gesture_label,
            self.detector_label,
            self.raw_label,
            self.stable_label,
            self.confidence_label,
            self.last_command_label,
            self.queue_label,
        ):
            widget.setObjectName("gestureDebugValue")
            layout.addWidget(widget)

        self.setStyleSheet(
            """
            QWidget#gestureDebugPanel {
                background-color: rgba(8, 15, 29, 156);
                border: 1px solid rgba(148, 163, 184, 18);
                border-radius: 12px;
            }
            QPushButton#gestureToggleButton {
                border: none;
                border-radius: 8px;
                padding: 4px 8px;
                font-size: 10px;
                font-weight: 700;
                text-align: center;
                letter-spacing: 0.4px;
            }
            QLabel#gestureDebugValue {
                color: #d5deea;
                background: transparent;
                font-size: 10px;
                font-weight: 600;
                letter-spacing: 0.2px;
            }
            """
        )
