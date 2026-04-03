from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any, Deque, Literal

import cv2
from app.models.gesture_behavior import GESTURE_BEHAVIOR_CONFIG, get_gesture_behavior
from app.utils.logging_utils import gesture_debug_log


DetectorStatus = Literal[
    "detector_ready",
    "detector_missing_dependency",
    "detector_init_failed",
    "detector_unavailable",
]


def _format_exception(exc: Exception | None) -> str | None:
    if exc is None:
        return None
    return f"{type(exc).__name__}: {exc}"


_MEDIAPIPE_IMPORT_ERROR: Exception | None = None

try:
    import mediapipe as mp
except Exception as exc:  # pragma: no cover - optional dependency
    mp = None
    _MEDIAPIPE_IMPORT_ERROR = exc

gesture_debug_log(
    "inference.mediapipe_import",
    success=_MEDIAPIPE_IMPORT_ERROR is None,
    error=_format_exception(_MEDIAPIPE_IMPORT_ERROR),
)
gesture_debug_log(
    "inference.module_loaded",
    file=__file__,
    module=__name__,
    sys_path0=sys.path[0] if sys.path else "",
)


@dataclass(slots=True)
class GestureInferenceResult:
    raw_gesture: str | None
    stable_gesture: str | None
    confidence: float | None
    command_name: str | None
    queue_state: str
    stable_hits: int
    required_hits: int
    required_confidence: float
    detector_available: bool
    detector_status: DetectorStatus
    detector_error: str | None
    detector_model_path: str | None


class GestureInferenceService:
    _NOISE_MARKER = "__noise__"
    _DEFAULT_MIN_CONFIDENCE = 0.72
    _GESTURE_COMMAND_MAP = {
        gesture_name: behavior.command for gesture_name, behavior in GESTURE_BEHAVIOR_CONFIG.items()
    }
    _INIT_LOGGED = False

    def __init__(
        self,
        stability_frames: int = 5,
        dominance_frames: int = 3,
        min_confidence: float = 0.68,
        noise_confidence_floor: float = 0.58,
        max_num_hands: int = 1,
        debug_bypass_stability: bool = False,
        debug_bypass_min_confidence: float = 0.55,
    ) -> None:
        self.stability_frames = max(1, int(stability_frames))
        self.dominance_frames = max(1, min(self.stability_frames, int(dominance_frames)))
        self.min_confidence = max(0.0, min(1.0, float(min_confidence)))
        self.noise_confidence_floor = max(0.0, min(1.0, float(noise_confidence_floor)))
        self.max_num_hands = max(1, int(max_num_hands))
        self.debug_bypass_stability = bool(debug_bypass_stability)
        self.debug_bypass_min_confidence = max(0.0, min(1.0, float(debug_bypass_min_confidence)))
        self._history: Deque[str | None] = deque(maxlen=self.stability_frames)
        self._gesture_command_map = dict(self._GESTURE_COMMAND_MAP)
        self._enabled_gesture_commands = set(self._gesture_command_map.keys())
        self._gesture_safety_rules = {
            "thumbs_up": {"min_confidence": 0.80, "required_hits": self.dominance_frames},
            "fist": {"min_confidence": 0.82, "required_hits": self.dominance_frames},
            "open_palm": {"min_confidence": 0.62, "required_hits": 2},
            "point_up": {"min_confidence": 0.76, "required_hits": self.dominance_frames},
        }
        self._fast_path_confidence = 0.88
        self._fast_path_hits = 2
        self._detector: Any | None = None
        self._detector_available = False
        self._detector_status: DetectorStatus = "detector_unavailable"
        self._detector_error: str | None = None
        self._model_path = self._resolve_model_path()
        self._init_attempted = False
        self._detector_unavailable_logged = False

        if not self.__class__._INIT_LOGGED:
            gesture_debug_log(
                "inference.instance_created",
                file=__file__,
                module=self.__class__.__module__,
                class_id=id(self.__class__),
                initialize_called=True,
                debug_bypass_stability=self.debug_bypass_stability,
                debug_bypass_min_confidence=self.debug_bypass_min_confidence,
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
                detector_available=self._detector_available,
                detector_status=self._detector_status,
                queue_state="idle",
            )
            return self._empty_result("idle")

        self.ensure_detector_initialized(reason="first_frame")
        gesture_debug_log(
            "inference.frame_received",
            frame_is_none=False,
            frame_shape=frame_shape,
            frame_dtype=frame_dtype,
            detector_available=self._detector_available,
            detector_status=self._detector_status,
        )

        if not self._detector_available or self._detector is None:
            self._log_detector_unavailable_once(frame_shape=frame_shape, frame_dtype=frame_dtype)
            return self._empty_result(self._detector_status)

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
                error=_format_exception(exc),
                detector_available=self._detector_available,
                detector_status=self._detector_status,
                queue_state="detector_error",
            )
            return self._empty_result("detector_error")

        try:
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            results = self._detector.detect(mp_image)
            gesture_debug_log(
                "inference.process_ok",
                frame_shape=frame_shape,
                frame_dtype=frame_dtype,
                process_ok=True,
            )
        except Exception as exc:
            gesture_debug_log(
                "inference.detector_error",
                frame_shape=frame_shape,
                frame_dtype=frame_dtype,
                process_ok=False,
                error=_format_exception(exc),
                detector_available=self._detector_available,
                detector_status=self._detector_status,
                queue_state="detector_error",
            )
            return self._empty_result("detector_error")

        hand_landmarks, handedness = self._extract_hand_landmarks(results)
        gesture_debug_log(
            "inference.landmarks_checked",
            landmarks_found=hand_landmarks is not None,
            handedness=handedness,
            detector_available=self._detector_available,
            detector_status=self._detector_status,
        )
        if hand_landmarks is None:
            self._history.append(None)
            gesture_debug_log(
                "inference.no_hand",
                raw_gesture="-",
                stable_gesture="-",
                confidence="-",
                resolved_command="-",
                queue_state="detecting",
                detector_available=self._detector_available,
                detector_status=self._detector_status,
            )
            return GestureInferenceResult(
                raw_gesture=None,
                stable_gesture=None,
                confidence=None,
                command_name=None,
                queue_state="detecting",
                stable_hits=0,
                required_hits=self.dominance_frames,
                required_confidence=self.min_confidence,
                detector_available=self._detector_available,
                detector_status=self._detector_status,
                detector_error=self._detector_error,
                detector_model_path=self._model_path,
            )

        raw_gesture, confidence = self._classify_landmarks(hand_landmarks, handedness)
        if raw_gesture is None:
            self._history.append(None)
            stable_gesture = self._stabilize_gesture()
            gesture_debug_log(
                "inference.unclassified",
                raw_gesture="-",
                stable_gesture=stable_gesture,
                confidence=confidence,
                resolved_command="-",
                queue_state="detecting",
                detector_available=self._detector_available,
                detector_status=self._detector_status,
            )
            return GestureInferenceResult(
                raw_gesture=None,
                stable_gesture=stable_gesture,
                confidence=confidence,
                command_name=None,
                queue_state="detecting",
                stable_hits=0,
                required_hits=self.dominance_frames,
                required_confidence=self.min_confidence,
                detector_available=self._detector_available,
                detector_status=self._detector_status,
                detector_error=self._detector_error,
                detector_model_path=self._model_path,
            )

        if confidence is None or confidence < self.noise_confidence_floor:
            self._history.append(self._NOISE_MARKER)
            stable_gesture = self._stabilize_gesture()
            gesture_debug_log(
                "inference.low_confidence",
                raw_gesture=raw_gesture,
                stable_gesture=stable_gesture,
                confidence=confidence,
                resolved_command="-",
                queue_state="low_confidence",
                detector_available=self._detector_available,
                detector_status=self._detector_status,
            )
            return GestureInferenceResult(
                raw_gesture=raw_gesture,
                stable_gesture=stable_gesture,
                confidence=confidence,
                command_name=None,
                queue_state="low_confidence",
                stable_hits=0,
                required_hits=self.dominance_frames,
                required_confidence=self.min_confidence,
                detector_available=self._detector_available,
                detector_status=self._detector_status,
                detector_error=self._detector_error,
                detector_model_path=self._model_path,
            )

        self._history.append(raw_gesture)
        stable_gesture, stable_hits = self._stabilize_gesture(with_count=True)
        command_name, queue_state, required_hits, required_confidence = self._resolve_command(
            raw_gesture,
            stable_gesture,
            stable_hits,
            confidence,
        )
        gesture_debug_log(
            "inference.resolved",
            raw_gesture=raw_gesture,
            stable_gesture=stable_gesture,
            confidence=confidence,
            resolved_command=command_name,
            queue_state=queue_state,
            stable_hits=stable_hits,
            required_hits=required_hits,
            required_confidence=required_confidence,
            debug_bypass_stability=self.debug_bypass_stability,
            detector_available=self._detector_available,
            detector_status=self._detector_status,
        )

        return GestureInferenceResult(
            raw_gesture=raw_gesture,
            stable_gesture=stable_gesture,
            confidence=confidence,
            command_name=command_name,
            queue_state=queue_state,
            stable_hits=stable_hits,
            required_hits=required_hits,
            required_confidence=required_confidence,
            detector_available=self._detector_available,
            detector_status=self._detector_status,
            detector_error=self._detector_error,
            detector_model_path=self._model_path,
        )

    def reset(self) -> None:
        self._history.clear()

    def is_detector_available(self) -> bool:
        self.ensure_detector_initialized(reason="status_check")
        return self._detector_available

    def get_detector_status(self) -> DetectorStatus:
        self.ensure_detector_initialized(reason="status_check")
        return self._detector_status

    def get_detector_error(self) -> str | None:
        self.ensure_detector_initialized(reason="status_check")
        return self._detector_error

    def get_model_path(self) -> str | None:
        return self._model_path

    def get_enabled_gesture_commands(self) -> dict[str, str]:
        return {
            gesture_name: command_name
            for gesture_name, command_name in self._gesture_command_map.items()
            if gesture_name in self._enabled_gesture_commands
        }

    def ensure_detector_initialized(self, *, reason: str) -> bool:
        if self._init_attempted:
            return self._detector_available
        self._init_attempted = True
        self._initialize_detector(reason=reason)
        return self._detector_available

    def _initialize_detector(self, *, reason: str) -> None:
        gesture_debug_log(
            "inference.detector_init_start",
            reason=reason,
            python=sys.executable,
            mediapipe_imported=mp is not None,
            mediapipe_version=getattr(mp, "__version__", None),
            model_path=self._model_path,
        )

        if mp is None:
            self._set_detector_failure(
                status="detector_missing_dependency",
                error=_format_exception(_MEDIAPIPE_IMPORT_ERROR) or "MediaPipe import failed",
                dependencies_available=False,
            )
            return

        try:
            from mediapipe.tasks.python.core.base_options import BaseOptions
            from mediapipe.tasks.python.vision import (
                HandLandmarker,
                HandLandmarkerOptions,
                RunningMode,
            )
        except Exception as exc:
            self._set_detector_failure(
                status="detector_missing_dependency",
                error=_format_exception(exc) or "MediaPipe Tasks API import failed",
                dependencies_available=False,
            )
            return

        if self._model_path is None:
            self._set_detector_failure(
                status="detector_init_failed",
                error="Gesture detector model path could not be resolved",
                dependencies_available=True,
            )
            return

        model_path = Path(self._model_path)
        if not model_path.is_file():
            self._set_detector_failure(
                status="detector_init_failed",
                error=f"Model file not found: {model_path}",
                dependencies_available=True,
            )
            return

        try:
            options = HandLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(model_path)),
                running_mode=RunningMode.IMAGE,
                num_hands=self.max_num_hands,
                min_hand_detection_confidence=0.5,
                min_tracking_confidence=0.5,
                min_hand_presence_confidence=0.5,
            )
            self._detector = HandLandmarker.create_from_options(options)
            self._detector_available = True
            self._detector_status = "detector_ready"
            self._detector_error = None
            gesture_debug_log(
                "inference.detector_init_success",
                detector_available=self._detector_available,
                detector_status=self._detector_status,
                dependencies_available=True,
                model_path=self._model_path,
                detector_type=type(self._detector).__name__,
            )
        except Exception as exc:
            self._set_detector_failure(
                status="detector_init_failed",
                error=_format_exception(exc) or "HandLandmarker creation failed",
                dependencies_available=True,
            )

    def _empty_result(self, queue_state: str) -> GestureInferenceResult:
        return GestureInferenceResult(
            raw_gesture=None,
            stable_gesture=None,
            confidence=None,
            command_name=None,
            queue_state=queue_state,
            stable_hits=0,
            required_hits=self.dominance_frames,
            required_confidence=self.min_confidence,
            detector_available=self._detector_available,
            detector_status=self._detector_status,
            detector_error=self._detector_error,
            detector_model_path=self._model_path,
        )

    def _extract_hand_landmarks(self, results: Any) -> tuple[Any | None, str | None]:
        if results is None:
            return None, None

        hand_landmarks = getattr(results, "hand_landmarks", None)
        if not hand_landmarks:
            return None, None

        handedness_label: str | None = None
        handedness_groups = getattr(results, "handedness", None)
        if handedness_groups:
            try:
                first_group = handedness_groups[0]
                if first_group:
                    first_category = first_group[0]
                    handedness_label = (
                        getattr(first_category, "category_name", None)
                        or getattr(first_category, "display_name", None)
                    )
            except Exception:
                handedness_label = None

        return hand_landmarks[0], handedness_label

    def _classify_landmarks(self, landmarks: Any, handedness: str | None) -> tuple[str | None, float | None]:
        points = self._landmark_points(landmarks)
        finger_states = self._finger_states(points, handedness)
        thumb_vertical = self._thumb_vertical_direction(points)
        thumb_horizontal = self._thumb_horizontal_direction(points)
        index_direction = self._index_direction(points)

        extended_count = sum(bool(value) for value in finger_states.values())
        other_folded = (
            not finger_states["index"]
            and not finger_states["middle"]
            and not finger_states["ring"]
            and not finger_states["pinky"]
        )
        index_above_middle = points[8].y < points[12].y - 0.03

        if finger_states["thumb"] and all(finger_states[name] for name in ("index", "middle", "ring", "pinky")):
            return "open_palm", 0.94

        if extended_count == 0:
            return "fist", 0.94

        if (
            finger_states["thumb"]
            and finger_states["index"]
            and not finger_states["middle"]
            and not finger_states["ring"]
            and not finger_states["pinky"]
        ):
            if thumb_horizontal == "right":
                return "l_shape_right", 0.89
            if thumb_horizontal == "left":
                return "l_shape_left", 0.89

        if (
            finger_states["index"]
            and not finger_states["middle"]
            and not finger_states["ring"]
            and not finger_states["pinky"]
            and not finger_states["thumb"]
        ):
            if index_direction == "up" and index_above_middle:
                return "point_up", 0.86
            if index_direction == "left":
                return "point_left", 0.86
            if index_direction == "right":
                return "point_right", 0.86

        if finger_states["thumb"] and other_folded:
            if thumb_vertical == "up":
                return "thumbs_up", 0.88

        if extended_count >= 4:
            return "open_palm", 0.68

        if extended_count <= 1:
            return "fist", 0.66

        return None, None

    def _finger_states(self, points: Any, handedness: str | None) -> dict[str, bool]:
        thumb = self._is_thumb_extended(points, handedness)
        return {
            "thumb": thumb,
            "index": points[8].y < points[6].y,
            "middle": points[12].y < points[10].y,
            "ring": points[16].y < points[14].y,
            "pinky": points[20].y < points[18].y,
        }

    def _is_thumb_extended(self, points: Any, handedness: str | None) -> bool:
        tip_x = points[4].x
        ip_x = points[3].x
        mcp_x = points[2].x

        if handedness == "Left":
            horizontal_extended = tip_x > ip_x > mcp_x
        elif handedness == "Right":
            horizontal_extended = tip_x < ip_x < mcp_x
        else:
            horizontal_extended = abs(tip_x - mcp_x) > 0.08

        vertical_extended = abs(points[4].y - points[2].y) > 0.12
        return horizontal_extended or vertical_extended

    def _thumb_vertical_direction(self, points: Any) -> str | None:
        thumb_tip_y = points[4].y
        thumb_ip_y = points[3].y
        thumb_mcp_y = points[2].y
        wrist_y = points[0].y

        if thumb_tip_y < thumb_ip_y < thumb_mcp_y and thumb_tip_y < wrist_y:
            return "up"
        if thumb_tip_y > thumb_ip_y > thumb_mcp_y and thumb_tip_y > wrist_y:
            return "down"
        return None

    def _thumb_horizontal_direction(self, points: Any) -> str | None:
        delta_x = points[4].x - points[2].x
        if delta_x >= 0.08:
            return "right"
        if delta_x <= -0.08:
            return "left"
        return None

    def _index_direction(self, points: Any) -> str | None:
        delta_x = points[8].x - points[5].x
        delta_y = points[8].y - points[5].y
        if abs(delta_x) > abs(delta_y) * 1.15:
            return "right" if delta_x > 0 else "left"
        if abs(delta_y) > abs(delta_x) * 1.15 and delta_y < 0:
            return "up"
        return None

    def _resolve_command(
        self,
        raw_gesture: str | None,
        stable_gesture: str | None,
        stable_hits: int,
        confidence: float | None,
    ) -> tuple[str | None, str, int, float]:
        if stable_gesture is None:
            if raw_gesture == "open_palm":
                safety_rule = self._gesture_safety_rules.get("open_palm", {})
                min_confidence = float(safety_rule.get("min_confidence", self.min_confidence))
                if confidence is not None and confidence >= min_confidence:
                    return "stop", "ready", 1, min_confidence
            if self.debug_bypass_stability:
                bypass_command = self._resolve_debug_bypass_command(raw_gesture, confidence)
                if bypass_command is not None:
                    return bypass_command, "debug_bypass", 1, self.debug_bypass_min_confidence
            if raw_gesture is None:
                return None, "detecting", self.dominance_frames, self.min_confidence
            return None, "stabilizing", self.dominance_frames, self.min_confidence

        behavior = get_gesture_behavior(stable_gesture)
        if behavior is None or stable_gesture not in self._enabled_gesture_commands:
            return None, "detecting", self.dominance_frames, self.min_confidence

        command_name = behavior.command
        if not command_name:
            return None, "stabilizing", self.dominance_frames, self.min_confidence

        safety_rule = self._gesture_safety_rules.get(stable_gesture, {})
        default_hits = self.dominance_frames
        default_confidence = self.min_confidence + (0.08 if behavior.behavior_type == "one_shot" else 0.04)
        min_confidence = float(safety_rule.get("min_confidence", default_confidence))
        required_hits = int(safety_rule.get("required_hits", default_hits))

        if confidence is None:
            return None, "low_confidence", required_hits, min_confidence
        if self.debug_bypass_stability and confidence >= self.debug_bypass_min_confidence:
            return command_name, "debug_bypass", required_hits, min_confidence
        if confidence < min_confidence:
            return None, "low_confidence", required_hits, min_confidence
        if behavior.behavior_type == "safety":
            return command_name, "ready", 1, min_confidence
        if confidence >= self._fast_path_confidence and stable_hits >= self._fast_path_hits:
            return command_name, "ready", self._fast_path_hits, min_confidence
        if stable_hits < required_hits:
            return None, "stabilizing", required_hits, min_confidence
        return command_name, "ready", required_hits, min_confidence

    def _resolve_debug_bypass_command(self, raw_gesture: str | None, confidence: float | None) -> str | None:
        if not self.debug_bypass_stability:
            return None
        if raw_gesture is None or confidence is None or confidence < self.debug_bypass_min_confidence:
            return None
        if raw_gesture not in self._enabled_gesture_commands:
            return None
        behavior = get_gesture_behavior(raw_gesture)
        return behavior.command if behavior is not None else None

    @classmethod
    def get_threshold_for_gesture(cls, stable_gesture: str | None) -> float:
        if not stable_gesture:
            return cls._DEFAULT_MIN_CONFIDENCE

        safety_rule = {
            "thumbs_up": {"min_confidence": 0.80},
            "fist": {"min_confidence": 0.82},
            "open_palm": {"min_confidence": 0.62},
            "point_up": {"min_confidence": 0.76},
        }.get(stable_gesture, {})
        behavior = get_gesture_behavior(stable_gesture)
        default_confidence = cls._DEFAULT_MIN_CONFIDENCE
        if behavior is not None and behavior.behavior_type == "one_shot":
            default_confidence += 0.08
        elif behavior is not None:
            default_confidence += 0.04
        return float(safety_rule.get("min_confidence", default_confidence))

    def _stabilize_gesture(self, with_count: bool = False) -> str | tuple[str | None, int] | None:
        if len(self._history) < self.dominance_frames:
            return (None, 0) if with_count else None

        counts: dict[str, int] = {}
        for item in self._history:
            if item is None or item == self._NOISE_MARKER:
                continue
            counts[item] = counts.get(item, 0) + 1

        if not counts:
            return (None, 0) if with_count else None

        stable_gesture, stable_hits = max(counts.items(), key=lambda entry: entry[1])
        if stable_hits < self.dominance_frames:
            return (None, stable_hits) if with_count else None

        return (stable_gesture, stable_hits) if with_count else stable_gesture

    def _set_detector_failure(
        self,
        *,
        status: DetectorStatus,
        error: str,
        dependencies_available: bool,
    ) -> None:
        self._detector = None
        self._detector_available = False
        self._detector_status = status
        self._detector_error = error
        gesture_debug_log(
            "inference.detector_init_failure",
            detector_available=self._detector_available,
            detector_status=self._detector_status,
            dependencies_available=dependencies_available,
            model_path=self._model_path,
            error=error,
        )

    def _log_detector_unavailable_once(self, *, frame_shape: Any, frame_dtype: Any) -> None:
        if self._detector_unavailable_logged:
            return
        self._detector_unavailable_logged = True
        gesture_debug_log(
            "inference.detector_unavailable",
            frame_shape=frame_shape,
            frame_dtype=frame_dtype,
            detector_available=self._detector_available,
            detector_status=self._detector_status,
            model_path=self._model_path,
            error=self._detector_error,
            queue_state=self._detector_status,
        )

    def _resolve_model_path(self) -> str:
        project_root = Path(__file__).resolve().parents[4]
        return str(project_root / "models" / "hand_landmarker.task")

    @staticmethod
    def _landmark_points(landmarks: Any) -> Any:
        return getattr(landmarks, "landmark", landmarks)
