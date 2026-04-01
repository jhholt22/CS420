from __future__ import annotations

from dataclasses import dataclass

from app.models.telemetry_state import TelemetryState


@dataclass(slots=True)
class AppState:
    connected: bool = False
    mode: str = "--"
    battery_pct: int | None = None
    height_cm: int | None = None
    stream_live: bool = False
    stream_status: str = "No Signal"
    gesture_enabled: bool = False
    last_error: str | None = None

    def update_from_telemetry(self, telemetry: TelemetryState) -> None:
        self.mode = telemetry.mode
        self.battery_pct = telemetry.battery_pct
        self.height_cm = telemetry.height_cm
        self.last_error = None

    def mark_connected(self, mode: str) -> None:
        self.connected = True
        self.mode = mode or "--"
        self.last_error = None

    def mark_disconnected(self, error: str | None = None) -> None:
        self.connected = False
        self.mode = "--"
        self.battery_pct = None
        self.height_cm = None
        self.last_error = error

    def set_stream_live(self, is_live: bool) -> None:
        self.stream_live = is_live

    def set_stream_status(self, status: str) -> None:
        self.stream_status = status.strip() if status else "No Signal"
        self.stream_live = self.stream_status == "Live"

    def reset_runtime_state(self) -> None:
        self.connected = False
        self.mode = "--"
        self.battery_pct = None
        self.height_cm = None
        self.stream_live = False
        self.stream_status = "Stopped"
        self.gesture_enabled = False
        self.last_error = None
