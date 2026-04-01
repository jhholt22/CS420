from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TelemetryState:
    battery_pct: int | None = None
    height_cm: int | None = None
    mode: str = "--"

    @classmethod
    def from_api(cls, status_data: dict, state_data: dict | None) -> TelemetryState:
        mode_value = status_data.get("mode") if isinstance(status_data, dict) else None
        mode = cls._coerce_text(mode_value) or "--"
        battery_pct = cls._coerce_int(state_data.get("battery_pct")) if isinstance(state_data, dict) else None
        height_cm = cls._coerce_int(state_data.get("height_cm")) if isinstance(state_data, dict) else None
        return cls(
            battery_pct=battery_pct,
            height_cm=height_cm,
            mode=mode,
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
