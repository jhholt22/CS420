from __future__ import annotations


class VideoStreamService:
    def __init__(self, stream_url: str = "") -> None:
        self.stream_url = stream_url
