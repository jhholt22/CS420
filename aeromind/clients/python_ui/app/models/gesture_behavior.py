from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.gestures.registry import GESTURE_REGISTRY

GestureBehaviorType = Literal["one_shot", "repeatable", "safety"]


@dataclass(frozen=True, slots=True)
class GestureBehavior:
    gesture: str
    command: str
    behavior_type: GestureBehaviorType
    cooldown_ms: int
    requires_release: bool

GESTURE_BEHAVIOR_CONFIG: dict[str, GestureBehavior] = {
    gesture.internal_name: GestureBehavior(
        gesture=gesture.internal_name,
        command=gesture.command,
        behavior_type=gesture.behavior_type,
        cooldown_ms=gesture.cooldown_ms,
        requires_release=gesture.requires_release,
    )
    for gesture in GESTURE_REGISTRY
}


def get_gesture_behavior(gesture_name: str | None) -> GestureBehavior | None:
    if gesture_name is None:
        return None
    normalized = str(gesture_name).strip().lower()
    if not normalized:
        return None
    return GESTURE_BEHAVIOR_CONFIG.get(normalized)
