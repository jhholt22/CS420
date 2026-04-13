from __future__ import annotations

from app.config import AppConfig
from app.gestures.types import DetectorStatus, GestureInferenceResult


def resolve_inference_state(
    *,
    config: AppConfig,
    dominance_frames: int,
    min_confidence: float,
    debug_bypass_stability: bool,
    debug_bypass_min_confidence: float,
    raw_gesture: str | None,
    stable_gesture: str | None,
    stable_hits: int,
    confidence: float | None,
) -> tuple[str, int, float]:
    if stable_gesture is None:
        if debug_bypass_stability and raw_gesture and confidence is not None and confidence >= debug_bypass_min_confidence:
            return "debug_bypass", 1, debug_bypass_min_confidence
        if raw_gesture is None:
            return "detecting", dominance_frames, min_confidence
        return "stabilizing", dominance_frames, config.gesture_min_confidence(raw_gesture)

    required_hits = dominance_frames
    required_confidence = config.gesture_min_confidence(stable_gesture)
    if confidence is None or confidence < required_confidence:
        return "low_confidence", required_hits, required_confidence
    return "ready", required_hits, required_confidence


def build_inference_result(
    *,
    raw_gesture: str | None,
    stable_gesture: str | None,
    confidence: float | None,
    command_name: str | None,
    queue_state: str,
    stable_hits: int,
    required_hits: int,
    required_confidence: float,
    detector_available: bool,
    detector_status: DetectorStatus,
    detector_error: str | None,
    detector_model_path: str | None,
) -> GestureInferenceResult:
    return GestureInferenceResult(
        raw_gesture=raw_gesture,
        stable_gesture=stable_gesture,
        confidence=confidence,
        command_name=command_name,
        queue_state=queue_state,
        stable_hits=stable_hits,
        required_hits=required_hits,
        required_confidence=required_confidence,
        detector_available=detector_available,
        detector_status=detector_status,
        detector_error=detector_error,
        detector_model_path=detector_model_path,
    )
