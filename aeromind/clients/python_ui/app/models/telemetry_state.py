from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TelemetryState:
    battery_pct: int | None = None
    height_cm: int | None = None
    mode: str = "--"
