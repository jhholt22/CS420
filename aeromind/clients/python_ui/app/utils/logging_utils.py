from __future__ import annotations

import os
from datetime import datetime
from typing import Any


def gesture_debug_log(stage: str, **fields: Any) -> None:
    if os.getenv("AEROMIND_GESTURE_DEBUG", "1").strip().lower() in {"0", "false", "off", "no"}:
        return

    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    parts = [f"{timestamp}", "[GESTUREDBG]", stage]

    if fields:
        payload = " ".join(f"{key}={_compact(value)}" for key, value in fields.items())
        parts.append(payload)

    print(" | ".join(parts), flush=True)


def _compact(value: Any) -> str:
    if value is None:
        return "-"
    text = str(value).strip()
    if not text:
        return "-"
    return text.replace(" ", "_")
