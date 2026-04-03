from __future__ import annotations

from typing import Any

from app.config import AppConfig
from app.services.api_client import ApiClient


class CommandController:
    """Wraps high-level system and flight actions."""

    def __init__(self, api_client: ApiClient, config: AppConfig | None = None) -> None:
        self.api_client = api_client
        self.config = config or AppConfig()

    def start_sim(self) -> dict[str, Any]:
        return self.api_client.start_controller("sim")

    def start_drone(self) -> dict[str, Any]:
        return self.api_client.start_controller("drone")

    def stop(self) -> dict[str, Any]:
        return self.api_client.stop_controller()

    def takeoff(self) -> dict[str, Any]:
        return self.send_named_command("takeoff")

    def land(self) -> dict[str, Any]:
        return self.send_named_command("land")

    def emergency(self) -> dict[str, Any]:
        return self.send_named_command("emergency")

    def execute_gesture_command(self, command_name: str) -> dict[str, Any]:
        if command_name == "takeoff":
            return self.takeoff()
        if command_name == "land":
            return self.land()
        if command_name == "emergency":
            return self.emergency()
        if command_name == "stop":
            return self.send_named_command("stop")
        if command_name in {"forward", "left", "right"}:
            return self.send_named_command(
                command_name,
                {"distance_cm": self.config.gesture_move_distance_cm},
            )
        if command_name == "rotate_right":
            return self.send_named_command(
                "cw",
                {"degrees": self.config.gesture_rotation_degrees},
            )
        if command_name == "rotate_left":
            return self.send_named_command(
                "ccw",
                {"degrees": self.config.gesture_rotation_degrees},
            )
        return self.send_named_command(command_name)

    def send_named_command(self, command: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.api_client.send_command(command, args)
