from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class CommandSpec:
    command: str
    label: str
    args: Dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict:
        return {
            "command": self.command,
            "args": dict(self.args),
        }


class GestureCommandMapper:
    """
    Maps stable gesture labels to API drone commands.

    Keep this small and dumb.
    Real behavior tuning belongs in config later, not in random UI code.
    """

    DEFAULT_MAP: Dict[str, CommandSpec] = {
        "PALM": CommandSpec(command="takeoff", label="Takeoff"),
        "FIST": CommandSpec(command="land", label="Land"),
        "THUMB_UP": CommandSpec(command="up", label="Up", args={"distance_cm": 30}),
        "THUMB_DOWN": CommandSpec(command="down", label="Down", args={"distance_cm": 30}),
        "POINT_LEFT": CommandSpec(command="", label="Left Disabled"),
        "POINT_RIGHT": CommandSpec(command="", label="Right Disabled"),
        "FORWARD": CommandSpec(command="forward", label="Forward", args={"distance_cm": 30}),
        "BACKWARD": CommandSpec(command="back", label="Back", args={"distance_cm": 30}),
        "ROTATE_LEFT": CommandSpec(command="ccw", label="Rotate Left", args={"degrees": 45}),
        "ROTATE_RIGHT": CommandSpec(command="cw", label="Rotate Right", args={"degrees": 45}),
        "STOP": CommandSpec(command="stop", label="Stop"),
        "NONE": CommandSpec(command="", label="No Action"),
    }

    def __init__(self, mapping: Optional[Dict[str, CommandSpec]] = None) -> None:
        self._mapping = mapping or self.DEFAULT_MAP.copy()

    def map_gesture(self, gesture: Optional[str]) -> Optional[CommandSpec]:
        if not gesture:
            return None

        key = gesture.strip().upper()
        spec = self._mapping.get(key)
        if not spec:
            return None

        if not spec.command:
            return None

        return spec

    def supported_gestures(self) -> list[str]:
        return sorted(self._mapping.keys())
