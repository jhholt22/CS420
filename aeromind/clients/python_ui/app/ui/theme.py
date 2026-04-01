from __future__ import annotations

from PySide6.QtWidgets import QApplication


def apply_dark_theme(app: QApplication) -> None:
    app.setStyleSheet(
        """
        QWidget {
            background-color: #0f172a;
            color: white;
            font-family: "Segoe UI";
            font-size: 14px;
        }

        QLabel {
            color: #e5e7eb;
            background: transparent;
        }

        #videoSurface {
            background-color: #020617;
        }

        #videoSurfaceLabel {
            color: #94a3b8;
            font-size: 30px;
            font-weight: 600;
            letter-spacing: 1px;
        }

        #videoOverlayContainer {
            background: transparent;
        }

        #videoStatusBadge {
            background-color: rgba(15, 23, 42, 220);
            color: #e2e8f0;
            border-radius: 12px;
            padding: 6px 10px;
        }

        #hudTopBar {
            background-color: rgba(15, 23, 42, 210);
            border-radius: 18px;
        }

        #hudTitle {
            color: #f8fafc;
            font-size: 22px;
            font-weight: 700;
        }

        #hudChip {
            background-color: rgba(30, 41, 59, 220);
            color: #e2e8f0;
            border-radius: 14px;
            padding: 8px 14px;
        }
        """
    )
