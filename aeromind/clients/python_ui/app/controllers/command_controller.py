from __future__ import annotations

from typing import Any

from app.services.api_client import ApiClient


class CommandController:
    """Wraps high-level system and flight actions."""

    def __init__(self, api_client: ApiClient) -> None:
        self.api_client = api_client

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
        return self.send_named_command(command_name)

    def send_named_command(self, command: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.api_client.send_command(command, args)
