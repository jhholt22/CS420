from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class GestureDebugPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("gestureDebugPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(4)

        self.gesture_label = QLabel("Gesture: OFF", self)
        self.raw_label = QLabel("Raw: -", self)
        self.stable_label = QLabel("Stable: -", self)
        self.last_command_label = QLabel("Last Command: -", self)
        self.queue_label = QLabel("Queue: idle", self)

        for widget in (
            self.gesture_label,
            self.raw_label,
            self.stable_label,
            self.last_command_label,
            self.queue_label,
        ):
            widget.setObjectName("gestureDebugValue")
            layout.addWidget(widget)

        self.setStyleSheet(
            """
            QWidget#gestureDebugPanel {
                background-color: rgba(15, 23, 42, 148);
                border: 1px solid rgba(148, 163, 184, 28);
                border-radius: 14px;
            }
            QLabel#gestureDebugValue {
                color: #cbd5e1;
                background: transparent;
                font-size: 11px;
                font-weight: 500;
            }
            """
        )
