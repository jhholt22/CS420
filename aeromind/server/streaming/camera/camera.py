from __future__ import annotations

from typing import Any

import cv2


class Camera:
    def __init__(self, index: int = 0, width: int = 640, height: int = 480):
        self.index = index
        self.width = width
        self.height = height
        self.cap: cv2.VideoCapture | None = None
        self.start()

    def start(self) -> bool:
        self.release()
        self.cap = cv2.VideoCapture(self.index)
        if not self.cap.isOpened():
            return False

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        return True

    def read(self) -> tuple[bool, Any]:
        if self.cap is None:
            return False, None
        ok, frame = self.cap.read()
        return ok, frame

    def release(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None