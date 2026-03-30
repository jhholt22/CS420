from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class CommandSpec:
    command: str
    label: str


class GestureCommandMapper:
    """
    Maps stable gesture labels to API drone commands.

    Keep this small and dumb.
    Real behavior tuning belongs in config later, not in random UI code.
    """

    DEFAULT_MAP: Dict[str, CommandSpec] = {
        "PALM": CommandSpec(command="takeoff", label="Takeoff"),
        "FIST": CommandSpec(command="land", label="Land"),
        "THUMB_UP": CommandSpec(command="up 30", label="Up"),
        "THUMB_DOWN": CommandSpec(command="down 30", label="Down"),
        "POINT_LEFT": CommandSpec(command="left 30", label="Left"),
        "POINT_RIGHT": CommandSpec(command="right 30", label="Right"),
        "FORWARD": CommandSpec(command="forward 30", label="Forward"),
        "BACKWARD": CommandSpec(command="back 30", label="Back"),
        "ROTATE_LEFT": CommandSpec(command="ccw 45", label="Rotate Left"),
        "ROTATE_RIGHT": CommandSpec(command="cw 45", label="Rotate Right"),
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