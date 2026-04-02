from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class GestureDebugPanel(QWidget):
    gestureToggleClicked = Signal()
    sessionStartClicked = Signal()
    sessionEndClicked = Signal()
    clearLabelClicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("gestureDebugPanel")
        self.setAttribute(Qt.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        self.gesture_toggle_button = QPushButton("GESTURE OFF", self)
        self.gesture_toggle_button.setObjectName("gestureToggleButton")
        self.gesture_toggle_button.setProperty("state", "off")
        self.gesture_toggle_button.clicked.connect(self.gestureToggleClicked)
        layout.addWidget(self.gesture_toggle_button)

        self.session_state_label = QLabel("Session: INACTIVE | Participant: P001 | Label: --", self)
        self.session_state_label.setObjectName("gestureDebugValue")
        layout.addWidget(self.session_state_label)

        session_grid = QGridLayout()
        session_grid.setContentsMargins(0, 0, 0, 0)
        session_grid.setHorizontalSpacing(6)
        session_grid.setVerticalSpacing(4)

        self.participant_input = QLineEdit("P001", self)
        self.participant_input.setPlaceholderText("Participant")
        self.participant_input.setObjectName("gestureSessionInput")

        self.lighting_input = QComboBox(self)
        self.lighting_input.setObjectName("gestureSessionInput")
        self.lighting_input.setEditable(True)
        self.lighting_input.addItems(["unknown", "bright", "normal", "dim"])
        self.lighting_input.setCurrentText("unknown")

        self.background_input = QComboBox(self)
        self.background_input.setObjectName("gestureSessionInput")
        self.background_input.setEditable(True)
        self.background_input.addItems(["unknown", "plain", "cluttered", "outdoor"])
        self.background_input.setCurrentText("unknown")

        self.distance_input = QLineEdit("", self)
        self.distance_input.setPlaceholderText("Distance m")
        self.distance_input.setObjectName("gestureSessionInput")

        self.notes_input = QLineEdit("", self)
        self.notes_input.setPlaceholderText("Notes")
        self.notes_input.setObjectName("gestureSessionInput")

        session_grid.addWidget(self._make_caption("ID"), 0, 0)
        session_grid.addWidget(self.participant_input, 0, 1)
        session_grid.addWidget(self._make_caption("Light"), 0, 2)
        session_grid.addWidget(self.lighting_input, 0, 3)
        session_grid.addWidget(self._make_caption("Bg"), 1, 0)
        session_grid.addWidget(self.background_input, 1, 1)
        session_grid.addWidget(self._make_caption("Dist"), 1, 2)
        session_grid.addWidget(self.distance_input, 1, 3)
        session_grid.addWidget(self._make_caption("Notes"), 2, 0)
        session_grid.addWidget(self.notes_input, 2, 1, 1, 3)
        layout.addLayout(session_grid)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(6)

        self.start_session_button = QPushButton("Start Session", self)
        self.start_session_button.setObjectName("gestureSessionButton")
        self.start_session_button.clicked.connect(self.sessionStartClicked)
        button_row.addWidget(self.start_session_button)

        self.end_session_button = QPushButton("End Session", self)
        self.end_session_button.setObjectName("gestureSessionButton")
        self.end_session_button.clicked.connect(self.sessionEndClicked)
        button_row.addWidget(self.end_session_button)

        self.clear_label_button = QPushButton("Clear Label", self)
        self.clear_label_button.setObjectName("gestureSessionButton")
        self.clear_label_button.clicked.connect(self.clearLabelClicked)
        button_row.addWidget(self.clear_label_button)

        layout.addLayout(button_row)

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
            QPushButton#gestureToggleButton,
            QPushButton#gestureSessionButton {
                border: none;
                border-radius: 8px;
                padding: 4px 8px;
                font-size: 10px;
                font-weight: 700;
                text-align: center;
                letter-spacing: 0.4px;
            }
            QPushButton#gestureSessionButton {
                background-color: rgba(30, 41, 59, 190);
                color: #d5deea;
            }
            QLabel#gestureDebugValue,
            QLabel#gestureSessionCaption {
                color: #d5deea;
                background: transparent;
                font-size: 10px;
                font-weight: 600;
                letter-spacing: 0.2px;
            }
            QLineEdit#gestureSessionInput,
            QComboBox#gestureSessionInput {
                background-color: rgba(15, 23, 42, 210);
                color: #e2e8f0;
                border: 1px solid rgba(148, 163, 184, 28);
                border-radius: 6px;
                padding: 3px 5px;
                font-size: 10px;
                min-height: 18px;
            }
            """
        )

    def _make_caption(self, text: str) -> QLabel:
        label = QLabel(text, self)
        label.setObjectName("gestureSessionCaption")
        return label

    def get_session_context(self) -> dict[str, str]:
        return {
            "participant_id": self.participant_input.text().strip() or "P001",
            "lighting": self.lighting_input.currentText().strip() or "unknown",
            "background": self.background_input.currentText().strip() or "unknown",
            "distance_m": self.distance_input.text().strip(),
            "notes": self.notes_input.text().strip(),
        }

    def set_session_context(
        self,
        *,
        participant_id: str,
        lighting: str,
        background: str,
        distance_m: str,
        notes: str,
    ) -> None:
        self.participant_input.setText(participant_id)
        self.lighting_input.setCurrentText(lighting)
        self.background_input.setCurrentText(background)
        self.distance_input.setText(distance_m)
        self.notes_input.setText(notes)
