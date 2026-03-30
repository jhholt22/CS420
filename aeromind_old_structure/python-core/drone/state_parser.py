from dataclasses import dataclass


@dataclass
class DroneTelemetry:
    battery_pct: int | None = None
    height_cm: int | None = None
    flight_state: str = "unknown"


class StateParser:
    @staticmethod
    def parse(raw: str) -> DroneTelemetry:
        data: dict[str, str] = {}
        for part in raw.strip().split(";"):
            if ":" not in part:
                continue
            k, v = part.split(":", 1)
            data[k] = v

        battery = None
        height = None

        if "bat" in data:
            try:
                battery = int(data["bat"])
            except Exception:
                battery = None

        if "h" in data:
            try:
                height = int(data["h"])
            except Exception:
                height = None

        if height is None:
            flight_state = "unknown"
        elif height > 20:
            flight_state = "flying"
        elif height <= 5:
            flight_state = "landed"
        else:
            flight_state = "near_ground"

        return DroneTelemetry(
            battery_pct=battery,
            height_cm=height,
            flight_state=flight_state,
        )
