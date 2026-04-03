from __future__ import annotations

from app.config import AppConfig
from app.controllers.command_controller import CommandController
from app.controllers.gesture_controller import GestureController
from app.controllers.rc_controller import RcController
from app.services.api_client import ApiClient


class AppController:
    """Composes the UI-facing controllers around one shared ApiClient."""

    def __init__(self, config: AppConfig | None = None, api_client: ApiClient | None = None) -> None:
        self.config = config or AppConfig()
        self.api_client = api_client or ApiClient(self.config.api_base_url)
        self.command_controller = CommandController(self.api_client, self.config)
        self.rc_controller = RcController(self.api_client)
        self.gesture_controller = GestureController()
