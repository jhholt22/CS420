from __future__ import annotations

import sys
from typing import Any

import cv2
from app.config import AppConfig
from app.gestures.gesture_direction_resolver import GestureDirectionResolver
from app.gestures.gesture_inference_state import build_inference_result, resolve_inference_state
from app.gestures.gesture_stabilizer import GestureStabilizer
from app.gestures.registry import GESTURE_REGISTRY
from app.gestures.types import DetectorStatus, GestureInferenceResult
from app.services.gesture_recognizer_runtime import GestureRecognizerRuntime
from app.utils.logging_utils import gesture_debug_log


gesture_debug_log(
    "inference.module_loaded",
    file=__file__,
    module=__name__,
    sys_path0=sys.path[0] if sys.path else "",
)


class GestureInferenceService:
    _NOISE_MARKER = "__noise__"
    _INIT_LOGGED = False

    def __init__(self, config: AppConfig | None = None) -> None:
        self._config = config or AppConfig()
        self.stability_frames = max(1, int(self._config.gesture_stability.stability_frames))
        self.dominance_frames = max(
            1,
            min(self.stability_frames, int(self._config.gesture_stability.dominance_frames)),
        )
        self.min_confidence = max(0.0, min(1.0, float(self._config.gesture_thresholds.default_min_confidence)))
        self.noise_confidence_floor = max(
            0.0,
            min(1.0, float(self._config.gesture_thresholds.noise_confidence_floor)),
        )
        self.debug_bypass_stability = bool(self._config.gesture_inference.debug_bypass_stability)
        self.debug_bypass_min_confidence = max(
            0.0,
            min(1.0, float(self._config.gesture_inference.debug_bypass_min_confidence)),
        )
        self._stabilizer = GestureStabilizer(
            stability_frames=self.stability_frames,
            dominance_frames=self.dominance_frames,
            noise_marker=self._NOISE_MARKER,
        )
        self._direction_resolver = GestureDirectionResolver(self._config)
        self._max_reliable_distance_m = float(self._config.gesture_environment.max_reliable_distance_m)
        self._distance_compensation_enabled = bool(self._config.gesture_environment.distance_compensation_enabled)
        self._runtime = GestureRecognizerRuntime(self._config)

        if not self.__class__._INIT_LOGGED:
            gesture_debug_log(
                "inference.instance_created",
                file=__file__,
                module=self.__class__.__module__,
                class_id=id(self.__class__),
                initialize_called=True,
                debug_bypass_stability=self.debug_bypass_stability,
                debug_bypass_min_confidence=self.debug_bypass_min_confidence,
                max_reliable_distance_m=self._max_reliable_distance_m,
                distance_compensation_enabled=self._distance_compensation_enabled,
            )
            self.__class__._INIT_LOGGED = True

        self.ensure_detector_initialized(reason="startup")

    def process_frame(self, frame: Any) -> GestureInferenceResult:
        frame_shape = getattr(frame, "shape", None)
        frame_dtype = getattr(frame, "dtype", None)
        if frame is None:
            gesture_debug_log(
                "inference.empty_frame",
                frame_is_none=True,
                detector_available=self._runtime.detector_available,
                detector_status=self._runtime.detector_status,
                queue_state="idle",
            )
            return self._empty_result("idle")

        self.ensure_detector_initialized(reason="first_frame")
        gesture_debug_log(
            "inference.frame_received",
            frame_is_none=False,
            frame_shape=frame_shape,
            frame_dtype=frame_dtype,
            detector_available=self._runtime.detector_available,
            detector_status=self._runtime.detector_status,
        )

        if not self._runtime.detector_available or self._runtime.detector is None:
            self._runtime.log_detector_unavailable_once(frame_shape=frame_shape, frame_dtype=frame_dtype)
            return self._empty_result(self._runtime.detector_status)

        try:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            gesture_debug_log(
                "inference.cvtcolor_ok",
                frame_shape=frame_shape,
                frame_dtype=frame_dtype,
            )
        except Exception as exc:
            gesture_debug_log(
                "inference.detector_error",
                frame_shape=frame_shape,
                frame_dtype=frame_dtype,
                cvtcolor_ok=False,
                error=f"{type(exc).__name__}: {exc}",
                detector_available=self._runtime.detector_available,
                detector_status=self._runtime.detector_status,
                queue_state="detector_error",
            )
            return self._empty_result("detector_error")

        try:
            recognition = self._runtime.recognize_rgb_frame(rgb_frame)
            recognizer_label = recognition.recognizer_label
            raw_gesture = recognition.mapped_gesture
            confidence = recognition.confidence
            gesture_debug_log(
                "inference.process_ok",
                frame_shape=frame_shape,
                frame_dtype=frame_dtype,
                process_ok=True,
                recognition_source="recognizer",
                recognizer_label=recognizer_label,
                raw_gesture=raw_gesture,
                confidence=confidence,
                tilt_value=recognition.tilt_value,
                raw_direction=recognition.raw_direction,
            )
        except Exception as exc:
            gesture_debug_log(
                "inference.detector_error",
                frame_shape=frame_shape,
                frame_dtype=frame_dtype,
                process_ok=False,
                error=f"{type(exc).__name__}: {exc}",
                detector_available=self._runtime.detector_available,
                detector_status=self._runtime.detector_status,
                queue_state="detector_error",
            )
            return self._empty_result("detector_error")

        if raw_gesture is None:
            self._stabilizer.observe(None)
            gesture_debug_log(
                "inference.recognizer_filtered",
                recognition_source="recognizer",
                recognizer_label=recognizer_label,
                mapped_gesture="-",
                raw_gesture="-",
                stable_gesture="-",
                confidence=confidence,
                threshold="-",
                resolved_command="-",
                queue_state="detecting",
                detector_available=self._runtime.detector_available,
                detector_status=self._runtime.detector_status,
            )
            return build_inference_result(
                raw_gesture=None,
                stable_gesture=None,
                confidence=None,
                command_name=None,
                queue_state="detecting",
                stable_hits=0,
                required_hits=self.dominance_frames,
                required_confidence=self.min_confidence,
                detector_available=self._runtime.detector_available,
                detector_status=self._runtime.detector_status,
                detector_error=self._runtime.detector_error,
                detector_model_path=self._runtime.model_path,
            )

        if confidence is None or confidence < self.noise_confidence_floor:
            self._stabilizer.observe_noise()
            threshold = self._config.gesture_min_confidence(raw_gesture)
            gesture_debug_log(
                "inference.low_confidence",
                recognition_source="recognizer",
                recognizer_label=recognizer_label,
                mapped_gesture=raw_gesture,
                raw_gesture=raw_gesture,
                stable_gesture="-",
                confidence=confidence,
                threshold=threshold,
                resolved_command="-",
                queue_state="low_confidence",
                detector_available=self._runtime.detector_available,
                detector_status=self._runtime.detector_status,
            )
            return build_inference_result(
                raw_gesture=raw_gesture,
                stable_gesture=None,
                confidence=confidence,
                command_name=None,
                queue_state="low_confidence",
                stable_hits=0,
                required_hits=self.dominance_frames,
                required_confidence=self.min_confidence,
                detector_available=self._runtime.detector_available,
                detector_status=self._runtime.detector_status,
                detector_error=self._runtime.detector_error,
                detector_model_path=self._runtime.model_path,
            )

        self._stabilizer.observe(raw_gesture)
        stable_gesture, stable_hits = self._stabilizer.stabilize()
        stable_gesture_out = stable_gesture
        if stable_gesture == "point_up":
            stable_gesture_out = self._resolve_point_up_direction(
                stable_gesture=stable_gesture,
                recognizer_label=recognizer_label,
                tilt_value=recognition.tilt_value,
                index_mcp_x=recognition.index_mcp_x,
                index_tip_x=recognition.index_tip_x,
            )

        queue_state, required_hits, required_confidence = resolve_inference_state(
            config=self._config,
            dominance_frames=self.dominance_frames,
            min_confidence=self.min_confidence,
            debug_bypass_stability=self.debug_bypass_stability,
            debug_bypass_min_confidence=self.debug_bypass_min_confidence,
            raw_gesture=raw_gesture,
            stable_gesture=stable_gesture_out,
            stable_hits=stable_hits,
            confidence=confidence,
        )
        stable_gesture_result = None if queue_state == "low_confidence" else stable_gesture_out

        gesture_debug_log(
            "inference.recognizer_mapped",
            recognition_source="recognizer",
            recognizer_label=recognizer_label,
            mapped_gesture=raw_gesture,
            confidence=confidence,
            threshold=required_confidence,
            queue_state=queue_state,
            tilt_value=recognition.tilt_value,
            raw_direction=recognition.raw_direction,
            detector_available=self._runtime.detector_available,
            detector_status=self._runtime.detector_status,
        )
        gesture_debug_log(
            "inference.resolved",
            recognition_source="recognizer",
            recognizer_label=recognizer_label,
            mapped_gesture=raw_gesture,
            raw_gesture=raw_gesture,
            stable_gesture=stable_gesture_result,
            confidence=confidence,
            resolved_command="-",
            queue_state=queue_state,
            stable_hits=stable_hits,
            required_hits=required_hits,
            required_confidence=required_confidence,
            tilt_value=recognition.tilt_value,
            raw_direction=recognition.raw_direction,
            index_mcp_x=recognition.index_mcp_x,
            index_tip_x=recognition.index_tip_x,
            debug_bypass_stability=self.debug_bypass_stability,
            detector_available=self._runtime.detector_available,
            detector_status=self._runtime.detector_status,
        )

        return build_inference_result(
            raw_gesture=raw_gesture,
            stable_gesture=stable_gesture_result,
            confidence=confidence,
            command_name=None,
            queue_state=queue_state,
            stable_hits=stable_hits,
            required_hits=required_hits,
            required_confidence=required_confidence,
            detector_available=self._runtime.detector_available,
            detector_status=self._runtime.detector_status,
            detector_error=self._runtime.detector_error,
            detector_model_path=self._runtime.model_path,
        )

    def reset(self) -> None:
        self._stabilizer.reset()
        self._direction_resolver.reset()

    def is_detector_available(self) -> bool:
        self.ensure_detector_initialized(reason="status_check")
        return self._runtime.detector_available

    def get_detector_status(self) -> DetectorStatus:
        self.ensure_detector_initialized(reason="status_check")
        return self._runtime.detector_status

    def get_detector_error(self) -> str | None:
        self.ensure_detector_initialized(reason="status_check")
        return self._runtime.detector_error

    def get_model_path(self) -> str | None:
        return self._runtime.model_path

    def get_enabled_gesture_commands(self) -> dict[str, str]:
        return {
            gesture.internal_name: gesture.command
            for gesture in GESTURE_REGISTRY
            if gesture.command is not None
        }

    def ensure_detector_initialized(self, *, reason: str) -> bool:
        return self._runtime.ensure_initialized(reason=reason)

    def _empty_result(self, queue_state: str) -> GestureInferenceResult:
        return build_inference_result(
            raw_gesture=None,
            stable_gesture=None,
            confidence=None,
            command_name=None,
            queue_state=queue_state,
            stable_hits=0,
            required_hits=self.dominance_frames,
            required_confidence=self.min_confidence,
            detector_available=self._runtime.detector_available,
            detector_status=self._runtime.detector_status,
            detector_error=self._runtime.detector_error,
            detector_model_path=self._runtime.model_path,
        )

    def _resolve_point_up_direction(
        self,
        *,
        stable_gesture: str,
        recognizer_label: str | None,
        tilt_value: float | None,
        index_mcp_x: float | None,
        index_tip_x: float | None,
    ) -> str:
        resolved_direction, direction_debug = self._direction_resolver.resolve(tilt_value=tilt_value)
        gesture_debug_log(
            "inference.direction_resolved",
            recognition_source="recognizer",
            recognizer_label=recognizer_label,
            mapped_gesture=stable_gesture,
            tilt_value=direction_debug["tilt_value"],
            smoothed_tilt=direction_debug["smoothed_tilt"],
            candidate_direction=direction_debug["candidate_direction"],
            resolved_direction=direction_debug["resolved_direction"],
            direction_reason=direction_debug["direction_reason"],
            index_mcp_x=index_mcp_x,
            index_tip_x=index_tip_x,
        )
        return resolved_direction
