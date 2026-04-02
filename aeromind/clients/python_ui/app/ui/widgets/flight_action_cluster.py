from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget


class FlightActionCluster(QWidget):
    takeoffClicked = Signal()
    landClicked = Signal()
    emergencyClicked = Signal()
    startSimClicked = Signal()
    startDroneClicked = Signal()
    stopClicked = Signal()
    rcIntervalChanged = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("flightActionCluster")
        self.setAttribute(Qt.WA_StyledBackground, True)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(6, 6, 6, 6)
        root_layout.setSpacing(4)

        top_row = QHBoxLayout()
        top_row.setSpacing(4)
        self.start_sim_button = self._make_button("START SIM", "secondary")
        self.start_drone_button = self._make_button("START DRONE", "secondary")
        self.stop_button = self._make_button("STOP", "secondary")
        top_row.addWidget(self.start_sim_button)
        top_row.addWidget(self.start_drone_button)
        top_row.addWidget(self.stop_button)
        root_layout.addLayout(top_row)

        main_grid = QGridLayout()
        main_grid.setHorizontalSpacing(4)
        main_grid.setVerticalSpacing(4)
        self.takeoff_button = self._make_button("TAKEOFF", "primary")
        self.land_button = self._make_button("LAND", "primary")
        self.emergency_button = self._make_button("EMERGENCY", "danger")
        main_grid.addWidget(self.takeoff_button, 0, 0)
        main_grid.addWidget(self.land_button, 0, 1)
        main_grid.addWidget(self.emergency_button, 1, 0, 1, 2)
        root_layout.addLayout(main_grid)

        interval_row = QHBoxLayout()
        interval_row.setSpacing(8)
        self.rc_interval_label = QLabel("RC Interval: 180 ms", self)
        self.rc_interval_label.setObjectName("rcIntervalLabel")
        self.rc_interval_slider = QSlider(Qt.Horizontal, self)
        self.rc_interval_slider.setObjectName("rcIntervalSlider")
        self.rc_interval_slider.setRange(80, 250)
        self.rc_interval_slider.setSingleStep(5)
        self.rc_interval_slider.setPageStep(10)
        self.rc_interval_slider.setValue(180)
        interval_row.addWidget(self.rc_interval_label)
        interval_row.addWidget(self.rc_interval_slider, 1)
        root_layout.addLayout(interval_row)

        self.start_sim_button.clicked.connect(self.startSimClicked)
        self.start_drone_button.clicked.connect(self.startDroneClicked)
        self.stop_button.clicked.connect(self.stopClicked)
        self.takeoff_button.clicked.connect(self.takeoffClicked)
        self.land_button.clicked.connect(self.landClicked)
        self.emergency_button.clicked.connect(self.emergencyClicked)
        self.rc_interval_slider.valueChanged.connect(self._on_rc_interval_changed)

        self.setStyleSheet(
            """
            QWidget#flightActionCluster {
                background-color: rgba(8, 15, 29, 92);
                border: 1px solid rgba(148, 163, 184, 16);
                border-radius: 12px;
            }
            QPushButton {
                border: none;
                border-radius: 8px;
                color: #f8fafc;
                font-size: 10px;
                font-weight: 700;
                padding: 5px 9px;
                letter-spacing: 0.35px;
            }
            QPushButton[variant="primary"] {
                background-color: rgba(37, 99, 235, 152);
            }
            QPushButton[variant="primary"]:hover {
                background-color: rgba(37, 99, 235, 178);
            }
            QPushButton[variant="danger"] {
                background-color: rgba(220, 38, 38, 194);
                padding: 6px 10px;
            }
            QPushButton[variant="danger"]:hover {
                background-color: rgba(220, 38, 38, 220);
            }
            QPushButton[variant="secondary"] {
                background-color: rgba(30, 41, 59, 134);
                color: #cbd5e1;
                padding: 4px 8px;
            }
            QPushButton[variant="secondary"]:hover {
                background-color: rgba(51, 65, 85, 162);
            }
            QLabel#rcIntervalLabel {
                color: #d5deea;
                background: transparent;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 0.2px;
                min-width: 106px;
            }
            QSlider#rcIntervalSlider::groove:horizontal {
                background-color: rgba(51, 65, 85, 170);
                border-radius: 3px;
                height: 6px;
            }
            QSlider#rcIntervalSlider::sub-page:horizontal {
                background-color: rgba(56, 189, 248, 196);
                border-radius: 3px;
            }
            QSlider#rcIntervalSlider::handle:horizontal {
                background-color: #f8fafc;
                border: 1px solid rgba(15, 23, 42, 140);
                border-radius: 6px;
                margin: -4px 0;
                width: 12px;
            }
            """
        )

    def _make_button(self, text: str, variant: str) -> QPushButton:
        button = QPushButton(text, self)
        button.setProperty("variant", variant)
        return button

    def set_rc_interval_value(self, value: int) -> None:
        value = max(80, min(250, int(value)))
        self.rc_interval_slider.blockSignals(True)
        self.rc_interval_slider.setValue(value)
        self.rc_interval_slider.blockSignals(False)
        self._update_rc_interval_label(value)

    def _on_rc_interval_changed(self, value: int) -> None:
        self._update_rc_interval_label(value)
        self.rcIntervalChanged.emit(value)

    def _update_rc_interval_label(self, value: int) -> None:
        self.rc_interval_label.setText(f"RC Interval: {int(value)} ms")
