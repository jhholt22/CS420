from __future__ import annotations

from typing import Any
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import cv2
from app.models.video_source import VideoSourceSpec
from app.utils.logging_utils import gesture_debug_log


class VideoStreamService:
    def __init__(
        self,
        default_source: VideoSourceSpec | str,
        *,
        prefer_ffmpeg: bool = True,
        max_width: int | None = None,
        max_height: int | None = None,
    ) -> None:
        self.prefer_ffmpeg = prefer_ffmpeg
        self.max_width = max_width
        self.max_height = max_height
        self._capture: cv2.VideoCapture | None = None
        self._current_source = self._coerce_source(default_source)

    def open_stream(self, source: VideoSourceSpec | str | int | None = None) -> bool:
        target_source = self._coerce_source(source) if source is not None else self._current_source
        self.close()
        self._current_source = target_source

        gesture_debug_log(
            "video.connect_attempt",
            source_kind=target_source.kind,
            source_value=target_source.value,
            source_label=target_source.label,
        )
        capture = self._open_capture(target_source)
        if capture is None or not capture.isOpened():
            if capture is not None:
                self._safe_release(capture)
            self._capture = None
            return False

        self._capture = capture
        self._configure_capture(self._capture)
        gesture_debug_log(
            "video.stream_open_success",
            source_kind=target_source.kind,
            source_value=target_source.value,
            source_label=target_source.label,
            is_open=self.is_open(),
        )
        return self.is_open()

    def read_frame(self) -> Any | None:
        if not self.is_open():
            return None

        assert self._capture is not None
        try:
            ok, frame = self._capture.read()
        except cv2.error as exc:
            gesture_debug_log(
                "video.frame_read_failed",
                source_kind=self._current_source.kind,
                source_value=self._current_source.value,
                error=repr(exc),
            )
            self.close()
            return None

        if not ok or frame is None:
            gesture_debug_log(
                "video.frame_empty",
                source_kind=self._current_source.kind,
                source_value=self._current_source.value,
            )
            self.close()
            return None
        return frame

    def is_open(self) -> bool:
        return self._capture is not None and self._capture.isOpened()

    def grab(self) -> bool:
        if not self.is_open():
            return False

        assert self._capture is not None
        try:
            return bool(self._capture.grab())
        except cv2.error as exc:
            gesture_debug_log(
                "video.frame_grab_failed",
                source_kind=self._current_source.kind,
                source_value=self._current_source.value,
                error=repr(exc),
            )
            return False

    def close(self) -> None:
        if self._capture is None:
            return
        gesture_debug_log(
            "video.capture_release_requested",
            source_kind=self._current_source.kind,
            source_value=self._current_source.value,
            source_label=self._current_source.label,
        )
        self._safe_release(self._capture)
        self._capture = None
        gesture_debug_log(
            "video.capture_released",
            source_kind=self._current_source.kind,
            source_value=self._current_source.value,
            source_label=self._current_source.label,
        )

    def probe_stream(self, source: VideoSourceSpec | str | int | None = None) -> bool:
        target_source = self._coerce_source(source) if source is not None else self._current_source
        if target_source.kind == "webcam":
            capture = self._try_open_webcam(int(target_source.value))
            if capture is None:
                return False
            self._safe_release(capture)
            return True
        target_url = str(target_source.value).strip()
        if not target_url:
            return False
        return self._is_stream_reachable(target_url)

    def current_source(self) -> VideoSourceSpec:
        return self._current_source

    def _open_capture(self, source: VideoSourceSpec) -> cv2.VideoCapture | None:
        if source.kind == "webcam":
            return self._open_webcam_capture(source)
        return self._open_mjpeg_capture(source)

    def _open_mjpeg_capture(self, source: VideoSourceSpec) -> cv2.VideoCapture | None:
        url = str(source.value).strip()
        if not url:
            gesture_debug_log("video.stream_open_failed", source_kind=source.kind, source_value=source.value, error="empty_url")
            return None
        if not self._is_stream_reachable(url):
            gesture_debug_log("video.stream_open_failed", source_kind=source.kind, source_value=source.value, error="unreachable")
            return None
        if self.prefer_ffmpeg:
            capture = self._try_open_url(url, cv2.CAP_FFMPEG)
            if capture is not None:
                return capture
        capture = self._try_open_url(url)
        if capture is None:
            gesture_debug_log("video.stream_open_failed", source_kind=source.kind, source_value=source.value, error="opencv_open_failed")
        return capture

    def _open_webcam_capture(self, source: VideoSourceSpec) -> cv2.VideoCapture | None:
        index = int(source.value)
        capture = self._try_open_webcam(index)
        if capture is None:
            gesture_debug_log(
                "video.webcam_open_failed",
                source_kind=source.kind,
                source_value=index,
                source_label=source.label,
            )
            return None
        gesture_debug_log(
            "video.webcam_open_success",
            source_kind=source.kind,
            source_value=index,
            source_label=source.label,
        )
        return capture

    @staticmethod
    def _try_open_url(url: str, backend: int | None = None) -> cv2.VideoCapture | None:
        try:
            capture = cv2.VideoCapture(url, backend) if backend is not None else cv2.VideoCapture(url)
        except cv2.error:
            return None

        if capture is None or not capture.isOpened():
            if capture is not None:
                try:
                    capture.release()
                except cv2.error:
                    pass
            return None
        return capture

    @staticmethod
    def _try_open_webcam(index: int) -> cv2.VideoCapture | None:
        backends: list[int | None] = [None]
        cap_dshow = getattr(cv2, "CAP_DSHOW", None)
        if cap_dshow is not None:
            backends.append(int(cap_dshow))

        for backend in backends:
            try:
                capture = cv2.VideoCapture(index, backend) if backend is not None else cv2.VideoCapture(index)
            except cv2.error:
                capture = None
            if capture is not None and capture.isOpened():
                return capture
            if capture is not None:
                try:
                    capture.release()
                except cv2.error:
                    pass
        return None

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
            except cv2.error:
                continue

    @staticmethod
    def _safe_release(capture: cv2.VideoCapture) -> None:
        try:
            capture.release()
        except cv2.error:
            gesture_debug_log("video.capture_release_failed")

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

    @staticmethod
    def _coerce_source(source: VideoSourceSpec | str | int) -> VideoSourceSpec:
        if isinstance(source, VideoSourceSpec):
            return source
        if isinstance(source, int):
            return VideoSourceSpec.webcam(source)
        return VideoSourceSpec.mjpeg(str(source))
