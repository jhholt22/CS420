from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GestureCandidate:
    gesture: str
    command: str
    stable_ms: int


class GestureMapper:
    """
    Maps raw gesture predictions → drone commands
    and tracks stability over time.
    """

    def __init__(self):
        self._last_gesture: str | None = None
        self._start_ts: int = 0

    def update(self, ts_ms: int, gesture: str) -> GestureCandidate:
        if gesture != self._last_gesture:
            self._last_gesture = gesture
            self._start_ts = ts_ms

        stable_ms = ts_ms - self._start_ts
        command = self._map_gesture_to_command(gesture)

        return GestureCandidate(
            gesture=gesture,
            command=command,
            stable_ms=stable_ms,
        )

    def _map_gesture_to_command(self, gesture: str) -> str:
        mapping = {
            "fist": "takeoff",
            "palm": "land",
            "thumb_up": "forward 50",
            "thumb_down": "back 50",
            "rotate_right": "cw 90",
            "rotate_left": "ccw 90",
        }

        return mapping.get(gesture, "none")