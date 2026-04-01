from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class StatusDrawer(QWidget):
    """Compact diagnostic drawer for optional runtime status details."""

    def __init__(self, title: str = "System Status", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("statusDrawer")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.title_label = QLabel(title, self)
        self.title_label.setObjectName("statusDrawerTitle")
        self.body_label = QLabel("No diagnostics available.", self)
        self.body_label.setObjectName("statusDrawerBody")
        self.body_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        layout.addWidget(self.title_label)
        layout.addWidget(self.body_label)

        self.setStyleSheet(
            """
            QWidget#statusDrawer {
                background-color: rgba(8, 15, 29, 168);
                border: 1px solid rgba(148, 163, 184, 22);
                border-radius: 12px;
            }
            QLabel#statusDrawerTitle {
                color: #f8fafc;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.4px;
            }
            QLabel#statusDrawerBody {
                color: #cbd5e1;
                font-size: 10px;
                font-weight: 500;
            }
            """
        )

    def set_status_lines(self, lines: list[str]) -> None:
        self.body_label.setText("\n".join(lines) if lines else "No diagnostics available.")
