from __future__ import annotations

from app.config import AppConfig


class AppController:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig()
