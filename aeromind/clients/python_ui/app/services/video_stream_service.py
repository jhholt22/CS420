from __future__ import annotations

from typing import Any
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import cv2
from app.utils.logging_utils import gesture_debug_log


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
        gesture_debug_log("thread.video_capture_opened", url=target_url, is_open=self.is_open())
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
            gesture_debug_log("thread.video_capture_close_requested", url=self.stream_url)
            self._safe_release(self._capture)
            self._capture = None

    def probe_stream(self, url: str | None = None) -> bool:
        target_url = (url or self.stream_url).strip()
        if not target_url:
            return False
        return self._is_stream_reachable(target_url)

    def _open_capture(self, url: str) -> cv2.VideoCapture | None:
        if not self._is_stream_reachable(url):
            gesture_debug_log("thread.video_capture_unreachable", url=url)
            return None
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
        for prop_name, value in (
            ("CAP_PROP_OPEN_TIMEOUT_MSEC", 2000),
            ("CAP_PROP_READ_TIMEOUT_MSEC", 1000),
        ):
            prop = getattr(cv2, prop_name, None)
            if prop is not None:
                settings.append((prop, float(value)))
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

    @staticmethod
    def _is_stream_reachable(url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return True
        try:
            request = Request(url, method="GET")
            with urlopen(request, timeout=1.0) as response:
                return bool(getattr(response, "status", 200) < 500)
        except (TimeoutError, URLError, OSError):
            return False
