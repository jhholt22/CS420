from __future__ import annotations

from PySide6.QtWidgets import QApplication


def apply_dark_theme(app: QApplication) -> None:
    app.setStyleSheet(
        """
        QWidget {
            background-color: #0f172a;
            color: #f8fafc;
            font-family: "Segoe UI";
            font-size: 13px;
        }

        QLabel {
            color: #dbe4f0;
            background: transparent;
        }

        #videoSurface {
            background-color: #020617;
        }

        #videoSurfaceLabel {
            color: rgba(148, 163, 184, 170);
            font-size: 18px;
            font-weight: 600;
            letter-spacing: 2px;
        }

        #videoOverlayContainer {
            background: transparent;
        }

        #videoStatusBadge {
            background-color: rgba(15, 23, 42, 176);
            color: #e2e8f0;
            border: 1px solid rgba(148, 163, 184, 50);
            border-radius: 10px;
            padding: 5px 10px;
            font-size: 11px;
            font-weight: 700;
        }

        #hudTopBar {
            background-color: rgba(15, 23, 42, 172);
            border: 1px solid rgba(148, 163, 184, 35);
            border-radius: 16px;
        }

        #hudTitle {
            color: #f8fafc;
            font-size: 18px;
            font-weight: 700;
            letter-spacing: 1px;
        }

        #hudChip {
            background-color: rgba(30, 41, 59, 150);
            color: #e2e8f0;
            border: 1px solid rgba(148, 163, 184, 28);
            border-radius: 11px;
            padding: 6px 10px;
            font-size: 11px;
            font-weight: 600;
        }
        """
    )
