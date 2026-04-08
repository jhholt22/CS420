from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget


class HudTopBar(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("hudTopBar")
        self._compact_mode = False
        self.setProperty("compact", False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 1, 0, 1)
        layout.setSpacing(10)
        self._layout = layout

        left_group = QHBoxLayout()
        left_group.setSpacing(6)
        self.connection_label = self._make_chip("Drone: Offline")
        self.sdk_label = self._make_chip("SDK: Unavailable")
        self.video_label = self._make_chip("Video: Offline")
        self.command_label = self._make_chip("Command: Idle")
        self.startup_label = self._make_chip("Startup: Pending")
        self.battery_label = self._make_chip("Battery: --")
        left_group.addWidget(self.connection_label)
        left_group.addWidget(self.sdk_label)
        left_group.addWidget(self.video_label)
        left_group.addWidget(self.command_label)
        left_group.addWidget(self.startup_label)
        left_group.addWidget(self.battery_label)

        self.title_label = QLabel("AeroMind", self)
        self.title_label.setObjectName("hudTitle")
        self.title_label.setAlignment(Qt.AlignCenter)

        right_group = QHBoxLayout()
        right_group.setSpacing(6)
        self.detector_label = self._make_chip("Detector: Unavailable")
        self.mode_label = self._make_chip("Mode: --")
        self.altitude_label = self._make_chip("Height: --")
        right_group.addWidget(self.detector_label)
        right_group.addWidget(self.mode_label)
        right_group.addWidget(self.altitude_label)
        self._chips = [
            self.connection_label,
            self.sdk_label,
            self.video_label,
            self.command_label,
            self.startup_label,
            self.battery_label,
            self.detector_label,
            self.mode_label,
            self.altitude_label,
        ]

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

    def set_compact_mode(self, compact: bool) -> None:
        compact = bool(compact)
        if compact == self._compact_mode:
            return
        self._compact_mode = compact
        self.setProperty("compact", compact)
        self._layout.setContentsMargins(0, 0 if compact else 1, 0, 0 if compact else 1)
        self._layout.setSpacing(6 if compact else 10)
        self.title_label.setProperty("compact", compact)
        for chip in self._chips:
            chip.setProperty("compact", compact)
            chip.style().unpolish(chip)
            chip.style().polish(chip)
        self.title_label.style().unpolish(self.title_label)
        self.title_label.style().polish(self.title_label)
        self.style().unpolish(self)
        self.style().polish(self)
        self.updateGeometry()
