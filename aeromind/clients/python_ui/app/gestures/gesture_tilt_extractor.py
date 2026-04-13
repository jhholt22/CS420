from __future__ import annotations

from typing import Any


def extract_point_up_tilt(result: Any) -> tuple[float | None, str | None, float | None, float | None]:
    try:
        hand_landmarks = getattr(result, "hand_landmarks", None)
        if not hand_landmarks or not hand_landmarks[0]:
            return None, None, None, None

        landmarks = hand_landmarks[0]
        index_mcp = landmarks[5]
        index_tip = landmarks[8]

        index_mcp_x = float(index_mcp.x)
        index_mcp_y = float(index_mcp.y)
        index_tip_x = float(index_tip.x)
        index_tip_y = float(index_tip.y)

        dx = index_tip_x - index_mcp_x
        dy = index_tip_y - index_mcp_y
        denom = abs(dx) + abs(dy) + 1e-6
        tilt_value = dx / denom

        if abs(tilt_value) < 0.08:
            raw_direction = "forward"
        elif tilt_value < 0:
            raw_direction = "left"
        else:
            raw_direction = "right"

        return tilt_value, raw_direction, index_mcp_x, index_tip_x
    except Exception:
        return None, None, None, None
