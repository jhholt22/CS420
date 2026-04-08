from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class GestureDebugPanel(QWidget):
    DEFAULT_MARGINS = (10, 8, 10, 8)
    COMPACT_MARGINS = (8, 6, 8, 6)

    gestureToggleClicked = Signal()
    sessionStartClicked = Signal()
    sessionEndClicked = Signal()
    clearLabelClicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("gestureDebugPanel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._compact_mode = False
        self._details_expanded = True
        self._auto_collapsed = False
        self.setProperty("compact", False)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        layout = QVBoxLayout(self)
        self.root_layout = layout
        layout.setContentsMargins(*self.DEFAULT_MARGINS)
        layout.setSpacing(4)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(6)

        self.gesture_toggle_button = QPushButton("GESTURE OFF", self)
        self.gesture_toggle_button.setObjectName("gestureToggleButton")
        self.gesture_toggle_button.setProperty("state", "off")
        self.gesture_toggle_button.clicked.connect(self.gestureToggleClicked)
        header_row.addWidget(self.gesture_toggle_button, 1)

        self.details_button = QPushButton("DETAILS ON", self)
        self.details_button.setObjectName("gestureDetailsButton")
        self.details_button.setCheckable(True)
        self.details_button.setChecked(True)
        self.details_button.clicked.connect(self._on_details_toggled)
        header_row.addWidget(self.details_button)
        layout.addLayout(header_row)

        self.session_state_label = QLabel("Session: INACTIVE | Participant: P001 | Label: --", self)
        self.session_state_label.setObjectName("gestureDebugValue")
        self.session_state_label.setWordWrap(True)
        layout.addWidget(self.session_state_label)

        self.summary_caption = QLabel("LIVE STATUS", self)
        self.summary_caption.setObjectName("gestureSectionCaption")
        layout.addWidget(self.summary_caption)

        self.gesture_label = QLabel("Gesture: OFF", self)
        self.detector_label = QLabel("Detector: OFFLINE", self)
        self.last_command_label = QLabel("Last Command: --", self)
        self.queue_label = QLabel("Queue: idle", self)

        for widget in (
            self.gesture_label,
            self.detector_label,
            self.last_command_label,
            self.queue_label,
        ):
            widget.setObjectName("gestureDebugValue")
            widget.setWordWrap(True)
            layout.addWidget(widget)

        self.details_container = QWidget(self)
        self.details_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        details_layout = QVBoxLayout(self.details_container)
        self.details_layout = details_layout
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(4)

        self.details_caption = QLabel("SESSION / DEBUG DETAILS", self)
        self.details_caption.setObjectName("gestureSectionCaption")
        details_layout.addWidget(self.details_caption)

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
        details_layout.addLayout(session_grid)

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
        details_layout.addLayout(button_row)

        self.raw_label = QLabel("Raw: --", self)
        self.stable_label = QLabel("Stable: --", self)
        self.confidence_label = QLabel("Confidence: --", self)

        for widget in (
            self.raw_label,
            self.stable_label,
            self.confidence_label,
        ):
            widget.setObjectName("gestureDebugValue")
            widget.setWordWrap(True)
            details_layout.addWidget(widget)

        layout.addWidget(self.details_container)

        self.setStyleSheet(
            """
            QWidget#gestureDebugPanel {
                background-color: rgba(8, 15, 29, 156);
                border: 1px solid rgba(148, 163, 184, 18);
                border-radius: 12px;
            }
            QWidget#gestureDebugPanel[compact="true"] {
                background-color: rgba(8, 15, 29, 136);
            }
            QPushButton#gestureToggleButton,
            QPushButton#gestureSessionButton,
            QPushButton#gestureDetailsButton {
                border: none;
                border-radius: 8px;
                padding: 4px 8px;
                font-size: 10px;
                font-weight: 700;
                text-align: center;
                letter-spacing: 0.4px;
                min-height: 28px;
            }
            QWidget#gestureDebugPanel[compact="true"] QPushButton#gestureToggleButton,
            QWidget#gestureDebugPanel[compact="true"] QPushButton#gestureSessionButton,
            QWidget#gestureDebugPanel[compact="true"] QPushButton#gestureDetailsButton {
                padding: 3px 7px;
                min-height: 26px;
            }
            QPushButton#gestureSessionButton {
                background-color: rgba(30, 41, 59, 190);
                color: #d5deea;
            }
            QPushButton#gestureDetailsButton {
                background-color: rgba(15, 23, 42, 210);
                color: #cbd5e1;
                min-width: 72px;
            }
            QLabel#gestureDebugValue,
            QLabel#gestureSessionCaption {
                color: #d5deea;
                background: transparent;
                font-size: 10px;
                font-weight: 600;
                letter-spacing: 0.2px;
            }
            QWidget#gestureDebugPanel[compact="true"] QLabel#gestureDebugValue {
                font-size: 9px;
            }
            QLabel#gestureSectionCaption {
                color: rgba(148, 163, 184, 210);
                background: transparent;
                font-size: 9px;
                font-weight: 700;
                letter-spacing: 1px;
                padding-top: 2px;
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
            QWidget#gestureDebugPanel[compact="true"] QLineEdit#gestureSessionInput,
            QWidget#gestureDebugPanel[compact="true"] QComboBox#gestureSessionInput {
                font-size: 9px;
                min-height: 16px;
                padding: 2px 4px;
            }
            """
        )
        self._refresh_details_visibility()

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

    def set_compact_mode(self, compact: bool) -> None:
        compact = bool(compact)
        if compact == self._compact_mode:
            return
        self._compact_mode = compact
        self.setProperty("compact", compact)
        if compact:
            if self._details_expanded:
                self._details_expanded = False
                self._auto_collapsed = True
            self.root_layout.setContentsMargins(*self.COMPACT_MARGINS)
            self.root_layout.setSpacing(3)
            self.details_layout.setSpacing(3)
        else:
            if self._auto_collapsed:
                self._details_expanded = True
                self._auto_collapsed = False
            self.root_layout.setContentsMargins(*self.DEFAULT_MARGINS)
            self.root_layout.setSpacing(4)
            self.details_layout.setSpacing(4)
        self.style().unpolish(self)
        self.style().polish(self)
        self._refresh_details_visibility()

    def set_details_expanded(self, expanded: bool) -> None:
        expanded = bool(expanded)
        if expanded == self._details_expanded:
            return
        self._auto_collapsed = False
        self._details_expanded = expanded
        self._refresh_details_visibility()

    def _on_details_toggled(self, checked: bool) -> None:
        self._details_expanded = bool(checked)
        self._refresh_details_visibility()

    def _refresh_details_visibility(self) -> None:
        show_details = self._details_expanded
        self.details_container.setVisible(show_details)
        self.details_button.setChecked(show_details)
        self.details_button.setText("DETAILS ON" if show_details else "DETAILS")
        self.details_button.setToolTip("Show or hide session and debug details.")
        self.updateGeometry()
