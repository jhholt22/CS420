from __future__ import annotations

from typing import Any

import cv2


class VideoStreamService:
    def __init__(
        self,
        stream_url: str,
        *,
        prefer_ffmpeg: bool = True,
        max_width: int | None = None,
        max_height: int | None = None,
    ) -> None:
        self.stream_url = stream_url
        self.prefer_ffmpeg = prefer_ffmpeg
        self.max_width = max_width
        self.max_height = max_height
        self._capture: cv2.VideoCapture | None = None

    def open_stream(self, url: str | None = None) -> bool:
        target_url = (url or self.stream_url).strip()
        if not target_url:
            self.close()
            return False

        self.close()
        self.stream_url = target_url

        capture = self._open_capture(target_url)
        if capture is None or not capture.isOpened():
            if capture is not None:
                self._safe_release(capture)
            self._capture = None
            return False

        self._capture = capture
        self._configure_capture(self._capture)
        return self.is_open()

    def read_frame(self) -> Any | None:
        if not self.is_open():
            return None

        try:
            assert self._capture is not None
            ok, frame = self._capture.read()
        except cv2.error:
            return None
        except Exception:
            return None

        if not ok or frame is None:
            self.close()
            return None
        return frame

    def is_open(self) -> bool:
        return self._capture is not None and self._capture.isOpened()

    def grab(self) -> bool:
        if not self.is_open():
            return False

        try:
            assert self._capture is not None
            return bool(self._capture.grab())
        except cv2.error:
            return False
        except Exception:
            return False

    def close(self) -> None:
        if self._capture is not None:
            self._safe_release(self._capture)
            self._capture = None

    def _open_capture(self, url: str) -> cv2.VideoCapture | None:
        if self.prefer_ffmpeg:
            capture = self._try_open(url, cv2.CAP_FFMPEG)
            if capture is not None:
                return capture
        return self._try_open(url)

    @staticmethod
    def _try_open(url: str, backend: int | None = None) -> cv2.VideoCapture | None:
        try:
            capture = cv2.VideoCapture(url, backend) if backend is not None else cv2.VideoCapture(url)
        except Exception:
            return None

        if capture is None or not capture.isOpened():
            if capture is not None:
                try:
                    capture.release()
                except Exception:
                    pass
            return None
        return capture

    def _configure_capture(self, capture: cv2.VideoCapture) -> None:
        settings: list[tuple[int, float]] = [(cv2.CAP_PROP_BUFFERSIZE, 1)]
        if self.max_width is not None:
            settings.append((cv2.CAP_PROP_FRAME_WIDTH, float(self.max_width)))
        if self.max_height is not None:
            settings.append((cv2.CAP_PROP_FRAME_HEIGHT, float(self.max_height)))

        for prop, value in settings:
            try:
                capture.set(prop, value)
            except Exception:
                continue

    @staticmethod
    def _safe_release(capture: cv2.VideoCapture) -> None:
        try:
            capture.release()
        except Exception:
            pass
