from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


GestureBehaviorType = Literal["one_shot", "repeatable", "safety"]


@dataclass(frozen=True, slots=True)
class GestureDefinition:
    internal_name: str
    recognizer_label: str | None
    command: str | None
    behavior_type: GestureBehaviorType
    cooldown_ms: int
    requires_release: bool
    confidence: float
    stabilization: int
    tilt_support: bool


GESTURE_REGISTRY: tuple[GestureDefinition, ...] = (
    GestureDefinition(
        internal_name="open_palm",
        recognizer_label="Open_Palm",
        command="hover",
        behavior_type="safety",
        cooldown_ms=0,
        requires_release=False,
        confidence=0.80,
        stabilization=320,
        tilt_support=False,
    ),
    GestureDefinition(
        internal_name="fist",
        recognizer_label="Closed_Fist",
        command="land",
        behavior_type="one_shot",
        cooldown_ms=1200,
        requires_release=False,
        confidence=0.72,
        stabilization=320,
        tilt_support=False,
    ),
    GestureDefinition(
        internal_name="victory",
        recognizer_label="Victory",
        command="takeoff",
        behavior_type="one_shot",
        cooldown_ms=1200,
        requires_release=False,
        confidence=0.78,
        stabilization=320,
        tilt_support=False,
    ),
    GestureDefinition(
        internal_name="point_up",
        recognizer_label="Pointing_Up",
        command="forward",
        behavior_type="repeatable",
        cooldown_ms=0,
        requires_release=False,
        confidence=0.78,
        stabilization=160,
        tilt_support=True,
    ),
    GestureDefinition(
        internal_name="point_left",
        recognizer_label=None,
        command="left",
        behavior_type="repeatable",
        cooldown_ms=0,
        requires_release=False,
        confidence=0.78,
        stabilization=160,
        tilt_support=False,
    ),
    GestureDefinition(
        internal_name="point_right",
        recognizer_label=None,
        command="right",
        behavior_type="repeatable",
        cooldown_ms=0,
        requires_release=False,
        confidence=0.78,
        stabilization=160,
        tilt_support=False,
    ),
)

_GESTURES_BY_INTERNAL_NAME = {gesture.internal_name: gesture for gesture in GESTURE_REGISTRY}
_GESTURES_BY_RECOGNIZER_LABEL = {
    gesture.recognizer_label: gesture
    for gesture in GESTURE_REGISTRY
    if gesture.recognizer_label is not None
}

SUPPORTED_GESTURES = frozenset(_GESTURES_BY_INTERNAL_NAME)


def get_gesture_definition(gesture_name: str | None) -> GestureDefinition | None:
    if gesture_name is None:
        return None
    normalized = str(gesture_name).strip().lower()
    if not normalized:
        return None
    return _GESTURES_BY_INTERNAL_NAME.get(normalized)


def get_gesture_definition_by_recognizer_label(recognizer_label: str | None) -> GestureDefinition | None:
    if recognizer_label is None:
        return None
    normalized = str(recognizer_label).strip()
    if not normalized:
        return None
    return _GESTURES_BY_RECOGNIZER_LABEL.get(normalized)
