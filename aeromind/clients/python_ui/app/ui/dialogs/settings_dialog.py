from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QSpinBox, QVBoxLayout, QWidget

from app.config import AppConfig


class SettingsDialog(QDialog):
    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Runtime Settings")
        self.setModal(True)
        self.resize(420, 220)

        self.api_base_url_edit = QLineEdit(config.api_base_url, self)
        self.video_url_edit = QLineEdit(config.video_url, self)
        self.status_refresh_ms_spin = QSpinBox(self)
        self.status_refresh_ms_spin.setRange(100, 10000)
        self.status_refresh_ms_spin.setValue(config.status_refresh_ms)
        self.video_reconnect_delay_ms_spin = QSpinBox(self)
        self.video_reconnect_delay_ms_spin.setRange(100, 10000)
        self.video_reconnect_delay_ms_spin.setValue(config.video_reconnect_delay_ms)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow("API Base URL", self.api_base_url_edit)
        form.addRow("Video URL", self.video_url_edit)
        form.addRow("Status Refresh (ms)", self.status_refresh_ms_spin)
        form.addRow("Video Reconnect (ms)", self.video_reconnect_delay_ms_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        self.setStyleSheet(
            """
            QDialog {
                background-color: #08101d;
                color: #e2e8f0;
            }
            QLineEdit, QSpinBox {
                background-color: rgba(15, 23, 42, 180);
                color: #f8fafc;
                border: 1px solid rgba(148, 163, 184, 28);
                border-radius: 8px;
                padding: 6px 8px;
            }
            QLabel {
                color: #cbd5e1;
            }
            QPushButton {
                border: none;
                border-radius: 8px;
                padding: 6px 10px;
                background-color: rgba(30, 41, 59, 160);
                color: #e2e8f0;
            }
            QPushButton:hover {
                background-color: rgba(51, 65, 85, 180);
            }
            """
        )

    def get_values(self) -> dict[str, str | int]:
        return {
            "api_base_url": self.api_base_url_edit.text().strip(),
            "video_url": self.video_url_edit.text().strip(),
            "status_refresh_ms": int(self.status_refresh_ms_spin.value()),
            "video_reconnect_delay_ms": int(self.video_reconnect_delay_ms_spin.value()),
        }
