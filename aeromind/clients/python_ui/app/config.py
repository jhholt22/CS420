from __future__ import annotations

from dataclasses import dataclass

API_BASE = "http://127.0.0.1:5000/api"
STATUS_REFRESH_MS = 1000
VIDEO_URL = "http://127.0.0.1:8080/video"
VIDEO_RECONNECT_DELAY_MS = 1000


@dataclass(slots=True)
class AppConfig:
    api_base_url: str = API_BASE
    video_url: str = VIDEO_URL
    status_refresh_ms: int = STATUS_REFRESH_MS
    video_reconnect_delay_ms: int = VIDEO_RECONNECT_DELAY_MS
