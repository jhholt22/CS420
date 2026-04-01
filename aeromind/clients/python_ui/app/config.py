from __future__ import annotations

from dataclasses import dataclass

API_BASE = "http://127.0.0.1:5000/api"
STATUS_REFRESH_MS = 1000
VIDEO_URL = "http://127.0.0.1:8080/video"
VIDEO_RECONNECT_DELAY_MS = 1000
VIDEO_READ_INTERVAL_MS = 30
VIDEO_MAX_WIDTH: int | None = None
VIDEO_MAX_HEIGHT: int | None = None
VIDEO_DROP_FRAMES_ON_RECONNECT = 3
VIDEO_BACKEND_PREFER_FFMPEG = True


@dataclass(slots=True)
class AppConfig:
    api_base_url: str = API_BASE
    video_url: str = VIDEO_URL
    status_refresh_ms: int = STATUS_REFRESH_MS
    video_reconnect_delay_ms: int = VIDEO_RECONNECT_DELAY_MS
    video_read_interval_ms: int = VIDEO_READ_INTERVAL_MS
    video_max_width: int | None = VIDEO_MAX_WIDTH
    video_max_height: int | None = VIDEO_MAX_HEIGHT
    video_drop_frames_on_reconnect: int = VIDEO_DROP_FRAMES_ON_RECONNECT
    video_backend_prefer_ffmpeg: bool = VIDEO_BACKEND_PREFER_FFMPEG
