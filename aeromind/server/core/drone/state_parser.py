from __future__ import annotations


def parse_state(raw: str) -> dict:
    values: dict[str, str] = {}

    for part in raw.strip().split(";"):
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        values[key] = value

    battery_pct = _safe_int(values.get("bat"))
    height_cm = _safe_int(values.get("h"))

    if height_cm is None:
        flight_state = "unknown"
    elif height_cm > 20:
        flight_state = "flying"
    elif height_cm <= 5:
        flight_state = "landed"
    else:
        flight_state = "near_ground"

    return {
        "battery_pct": battery_pct,
        "height_cm": height_cm,
        "flight_state": flight_state,
        "raw": raw,
    }


def _safe_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None