from dataclasses import dataclass

@dataclass
class CommandCandidate:
    command: str          # tello command string or logical command
    stable_ms: int

class GestureMapper:
    def __init__(self):
        self._last_gesture = "none"
        self._last_change_ts = None

    def update(self, ts_ms: int, gesture: str) -> CommandCandidate:
        if self._last_change_ts is None:
            self._last_change_ts = ts_ms

        if gesture != self._last_gesture:
            self._last_gesture = gesture
            self._last_change_ts = ts_ms

        stable_ms = ts_ms - self._last_change_ts
        cmd = self._map_gesture_to_command(gesture)
        return CommandCandidate(cmd, stable_ms)

    def _map_gesture_to_command(self, gesture: str) -> str:
        return {
            "takeoff": "takeoff",
            "land": "land",
            "forward": "forward 20",
            "backward": "back 20",
            "rotate_left": "ccw 30",
            "emergency_stop": "emergency",
            "none": "none",
        }.get(gesture, "none")
