from __future__ import annotations

from typing import Any

from app.config import AppConfig
from app.models.rc_state import RcState
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
        if command_name in {"stop", "hover"}:
            return self.send_named_command(
                "rc",
                {"left_right": 0, "forward_back": 0, "up_down": 0, "yaw": 0},
            )
        movement_state = self.build_gesture_movement_state(command_name)
        if movement_state is not None:
            payload = movement_state.to_payload()
            return self.send_named_command(
                "rc",
                {
                    "left_right": payload["lr"],
                    "forward_back": payload["fb"],
                    "up_down": payload["ud"],
                    "yaw": payload["yaw"],
                },
            )
        return self.send_named_command(command_name)

    def build_gesture_movement_state(self, command_name: str) -> RcState | None:
        # Gesture motion RC shaping is controlled by AppConfig.gesture_motion.
        speed = max(0, min(100, int(self.config.gesture_rc_speed_for_command(command_name))))
        if command_name in {"stop", "hover"}:
            return RcState()
        if command_name == "forward":
            return RcState(fb=speed)
        if command_name == "back":
            return RcState(fb=-speed)
        if command_name == "left":
            return RcState(lr=-speed)
        if command_name == "right":
            return RcState(lr=speed)
        if command_name == "up":
            return RcState(ud=speed)
        if command_name == "down":
            return RcState(ud=-speed)
        if command_name == "rotate_right":
            return RcState(yaw=speed)
        if command_name == "rotate_left":
            return RcState(yaw=-speed)
        return None

    def send_named_command(self, command: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.api_client.send_command(command, args)
