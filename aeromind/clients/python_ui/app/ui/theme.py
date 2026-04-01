from __future__ import annotations

from PySide6.QtWidgets import QApplication


def apply_dark_theme(app: QApplication) -> None:
    app.setStyleSheet(
        """
        QWidget {
            background-color: #050b16;
            color: #f8fafc;
            font-family: "Segoe UI";
            font-size: 13px;
        }

        QLabel {
            color: #d7dfeb;
            background: transparent;
        }

        #videoSurface {
            background-color: #020611;
        }

        #videoSurfaceLabel {
            color: rgba(148, 163, 184, 150);
            font-size: 13px;
            font-weight: 600;
            letter-spacing: 2px;
        }

        #videoOverlayContainer {
            background: transparent;
        }

        #videoStatusBadge {
            background-color: rgba(6, 12, 24, 182);
            color: #dbe7f5;
            border: 1px solid rgba(148, 163, 184, 42);
            border-radius: 9px;
            padding: 4px 10px;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 1px;
        }

        #hudTopBar {
            background: transparent;
            border: none;
        }

        #hudTitle {
            color: #f8fafc;
            font-size: 17px;
            font-weight: 700;
            letter-spacing: 2px;
        }

        #hudChip {
            background-color: rgba(8, 15, 29, 146);
            color: #dbe6f2;
            border: 1px solid rgba(148, 163, 184, 22);
            border-radius: 9px;
            padding: 4px 10px;
            font-size: 10px;
            font-weight: 700;
        }

        #gestureToggleButton[state="off"] {
            background-color: rgba(30, 41, 59, 150);
            color: #d7dfeb;
            border: 1px solid rgba(148, 163, 184, 20);
        }

        #gestureToggleButton[state="off"]:hover {
            background-color: rgba(51, 65, 85, 172);
        }

        #gestureToggleButton[state="on"] {
            background-color: rgba(14, 116, 144, 184);
            color: #f8fafc;
            border: 1px solid rgba(103, 232, 249, 38);
        }

        #gestureToggleButton[state="on"]:hover {
            background-color: rgba(8, 145, 178, 204);
        }
        """
    )
