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
            color: rgba(226, 232, 240, 210);
            font-size: 14px;
            font-weight: 700;
            letter-spacing: 2px;
        }

        #videoSurfaceSubtext {
            color: rgba(148, 163, 184, 170);
            font-size: 10px;
            font-weight: 500;
            letter-spacing: 0.8px;
        }

        #videoOverlayContainer {
            background: transparent;
        }

        #videoStatusBadge {
            background-color: rgba(6, 12, 24, 190);
            color: #dbe7f5;
            border: 1px solid rgba(148, 163, 184, 38);
            border-radius: 8px;
            padding: 3px 10px;
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
            font-size: 16px;
            font-weight: 700;
            letter-spacing: 2.4px;
        }

        #hudTitleAccent {
            color: rgba(125, 211, 252, 220);
        }

        #hudChip {
            background-color: rgba(8, 15, 29, 152);
            color: #dbe6f2;
            border: 1px solid rgba(148, 163, 184, 20);
            border-radius: 8px;
            padding: 3px 10px;
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
            border: 1px solid rgba(103, 232, 249, 36);
        }

        #gestureToggleButton[state="on"]:hover {
            background-color: rgba(8, 145, 178, 204);
        }
        """
    )
