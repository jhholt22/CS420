from __future__ import annotations

from PySide6.QtCore import QObject


class VideoWorker(QObject):
    def __init__(self) -> None:
        super().__init__()
