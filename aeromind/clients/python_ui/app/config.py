from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class AppConfig:
    api_base_url: str = ""
    video_url: str = ""
