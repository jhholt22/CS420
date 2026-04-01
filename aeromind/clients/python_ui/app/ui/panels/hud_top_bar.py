from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget


class HudTopBar(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("hudTopBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(12)

        left_group = QHBoxLayout()
        left_group.setSpacing(6)
        self.connection_label = self._make_chip("Connection: Disconnected")
        self.battery_label = self._make_chip("Battery: --")
        left_group.addWidget(self.connection_label)
        left_group.addWidget(self.battery_label)

        self.title_label = QLabel("AeroMind", self)
        self.title_label.setObjectName("hudTitle")
        self.title_label.setAlignment(Qt.AlignCenter)

        right_group = QHBoxLayout()
        right_group.setSpacing(6)
        self.mode_label = self._make_chip("Mode: --")
        self.altitude_label = self._make_chip("Height: --")
        right_group.addWidget(self.mode_label)
        right_group.addWidget(self.altitude_label)

        left_widget = QWidget(self)
        left_widget.setLayout(left_group)
        left_widget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

        center_widget = QWidget(self)
        center_layout = QHBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.addWidget(self.title_label)

        right_widget = QWidget(self)
        right_widget.setLayout(right_group)
        right_widget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

        layout.addWidget(left_widget, 0, Qt.AlignLeft)
        layout.addWidget(center_widget, 1)
        layout.addWidget(right_widget, 0, Qt.AlignRight)

    def _make_chip(self, text: str) -> QLabel:
        chip = QLabel(text, self)
        chip.setObjectName("hudChip")
        chip.setAlignment(Qt.AlignCenter)
        return chip
