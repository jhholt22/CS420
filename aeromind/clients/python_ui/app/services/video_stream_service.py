from __future__ import annotations

from typing import Any

import cv2


class VideoStreamService:
    def __init__(self, stream_url: str) -> None:
        self.stream_url = stream_url
        self._capture: cv2.VideoCapture | None = None

    def open_stream(self, url: str) -> bool:
        self.close()
        self.stream_url = url
        self._capture = cv2.VideoCapture(url)
        return bool(self._capture and self._capture.isOpened())

    def read_frame(self) -> Any | None:
        if self._capture is None or not self._capture.isOpened():
            return None

        try:
            ok, frame = self._capture.read()
        except cv2.error:
            return None

        if not ok or frame is None:
            return None
        return frame

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None
