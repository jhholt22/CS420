from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = [
    "DetectorStatus",
    "GESTURE_REGISTRY",
    "GestureDirectionResolver",
    "GestureDefinition",
    "GestureInferenceResult",
    "GestureStabilizer",
    "RawGestureSample",
    "SUPPORTED_GESTURES",
    "get_gesture_definition",
    "get_gesture_definition_by_recognizer_label",
]

if TYPE_CHECKING:
    from app.gestures.gesture_direction_resolver import GestureDirectionResolver
    from app.gestures.gesture_stabilizer import GestureStabilizer
    from app.gestures.registry import (
        GESTURE_REGISTRY,
        GestureDefinition,
        SUPPORTED_GESTURES,
        get_gesture_definition,
        get_gesture_definition_by_recognizer_label,
    )
    from app.gestures.types import DetectorStatus, GestureInferenceResult, RawGestureSample


def __getattr__(name: str) -> Any:
    if name == "GestureDirectionResolver":
        from app.gestures.gesture_direction_resolver import GestureDirectionResolver

        return GestureDirectionResolver
    if name == "GestureStabilizer":
        from app.gestures.gesture_stabilizer import GestureStabilizer

        return GestureStabilizer
    if name in {
        "GESTURE_REGISTRY",
        "GestureDefinition",
        "SUPPORTED_GESTURES",
        "get_gesture_definition",
        "get_gesture_definition_by_recognizer_label",
    }:
        from app.gestures import registry as _registry

        return getattr(_registry, name)
    if name in {"DetectorStatus", "GestureInferenceResult", "RawGestureSample"}:
        from app.gestures import types as _types

        return getattr(_types, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
