from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QPushButton, QVBoxLayout, QWidget


class FlightActionCluster(QWidget):
    takeoffClicked = Signal()
    landClicked = Signal()
    emergencyClicked = Signal()
    startSimClicked = Signal()
    startDroneClicked = Signal()
    stopClicked = Signal()

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

        self.start_sim_button.clicked.connect(self.startSimClicked)
        self.start_drone_button.clicked.connect(self.startDroneClicked)
        self.stop_button.clicked.connect(self.stopClicked)
        self.takeoff_button.clicked.connect(self.takeoffClicked)
        self.land_button.clicked.connect(self.landClicked)
        self.emergency_button.clicked.connect(self.emergencyClicked)

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
            """
        )

    def _make_button(self, text: str, variant: str) -> QPushButton:
        button = QPushButton(text, self)
        button.setProperty("variant", variant)
        return button
