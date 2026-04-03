from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TelemetryState:
    battery_pct: int | None = None
    height_cm: int | None = None
    mode: str = "--"
    drone_connected: bool = False
    sdk_mode_ready: bool = False

    @classmethod
    def from_api(
        cls,
        status_data: dict,
        state_data: dict | None,
        diag_data: dict | None = None,
    ) -> TelemetryState:
        mode_value = state_data.get("mode") if isinstance(state_data, dict) else None
        if mode_value is None and isinstance(status_data, dict):
            mode_value = status_data.get("mode")
        mode = cls._coerce_text(mode_value) or "--"
        battery_pct = cls._coerce_int(state_data.get("battery_pct")) if isinstance(state_data, dict) else None
        height_cm = cls._coerce_int(state_data.get("height_cm")) if isinstance(state_data, dict) else None
        drone_connected = bool(
            isinstance(diag_data, dict) and diag_data.get("connected")
        ) or bool(isinstance(status_data, dict) and status_data.get("running"))
        sdk_mode_ready = bool(isinstance(diag_data, dict) and diag_data.get("sdk_mode"))
        return cls(
            battery_pct=battery_pct,
            height_cm=height_cm,
            mode=mode,
            drone_connected=drone_connected,
            sdk_mode_ready=sdk_mode_ready,
        )

    @staticmethod
    def _coerce_int(value: object) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_text(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text or text.lower() == "none":
            return None
        return text
