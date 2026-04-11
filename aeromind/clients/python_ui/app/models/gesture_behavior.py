from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


GestureBehaviorType = Literal["one_shot", "repeatable", "safety"]


@dataclass(frozen=True, slots=True)
class GestureBehavior:
    gesture: str
    command: str
    behavior_type: GestureBehaviorType
    cooldown_ms: int
    requires_release: bool


GESTURE_BEHAVIOR_CONFIG: dict[str, GestureBehavior] = {
    "open_palm": GestureBehavior(
        gesture="open_palm",
        command="takeoff",
        behavior_type="one_shot",
        cooldown_ms=2200,
        requires_release=True,
    ),
    "point_down": GestureBehavior(
        gesture="point_down",
        command="land",
        behavior_type="one_shot",
        cooldown_ms=1800,
        requires_release=True,
    ),
    "fist": GestureBehavior(
        gesture="fist",
        command="hover",
        behavior_type="safety",
        cooldown_ms=0,
        requires_release=False,
    ),
    "thumbs_up": GestureBehavior(
        gesture="thumbs_up",
        command="hover",
        behavior_type="safety",
        cooldown_ms=0,
        requires_release=False,
    ),
    "point_up": GestureBehavior(
        gesture="point_up",
        command="forward",
        behavior_type="repeatable",
        cooldown_ms=700,
        requires_release=False,
    ),
    "point_left": GestureBehavior(
        gesture="point_left",
        command="left",
        behavior_type="repeatable",
        cooldown_ms=700,
        requires_release=False,
    ),
    "point_right": GestureBehavior(
        gesture="point_right",
        command="right",
        behavior_type="repeatable",
        cooldown_ms=700,
        requires_release=False,
    ),
    "l_shape_right": GestureBehavior(
        gesture="l_shape_right",
        command="up",
        behavior_type="repeatable",
        cooldown_ms=700,
        requires_release=False,
    ),
    "l_shape_left": GestureBehavior(
        gesture="l_shape_left",
        command="down",
        behavior_type="repeatable",
        cooldown_ms=700,
        requires_release=False,
    ),
}


def get_gesture_behavior(gesture_name: str | None) -> GestureBehavior | None:
    if gesture_name is None:
        return None
    normalized = str(gesture_name).strip().lower()
    if not normalized:
        return None
    return GESTURE_BEHAVIOR_CONFIG.get(normalized)
