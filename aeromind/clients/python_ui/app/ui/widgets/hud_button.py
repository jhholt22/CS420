from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QWidget


class HudButton(QPushButton):
    def __init__(
        self,
        text: str,
        variant: str = "secondary",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setProperty("variant", variant)
        self.setObjectName("hudButton")
        self._apply_style()

    def set_variant(self, variant: str) -> None:
        self.setProperty("variant", variant)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QPushButton#hudButton {
                border: none;
                border-radius: 8px;
                color: #f8fafc;
                font-size: 10px;
                font-weight: 700;
                padding: 6px 9px;
                letter-spacing: 0.4px;
                background-color: rgba(30, 41, 59, 136);
            }
            QPushButton#hudButton[variant="secondary"] {
                background-color: rgba(30, 41, 59, 136);
                color: #cbd5e1;
            }
            QPushButton#hudButton[variant="secondary"]:hover {
                background-color: rgba(51, 65, 85, 164);
            }
            QPushButton#hudButton[variant="primary"] {
                background-color: rgba(37, 99, 235, 148);
            }
            QPushButton#hudButton[variant="primary"]:hover {
                background-color: rgba(37, 99, 235, 176);
            }
            QPushButton#hudButton[variant="danger"] {
                background-color: rgba(220, 38, 38, 186);
            }
            QPushButton#hudButton[variant="danger"]:hover {
                background-color: rgba(220, 38, 38, 214);
            }
            """
        )
