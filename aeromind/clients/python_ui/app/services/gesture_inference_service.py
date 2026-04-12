from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
import sys
from threading import Condition
from time import monotonic
from typing import Any, Deque, Literal

import cv2
from app.config import AppConfig
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
    _RECOGNIZER_RESULT_TIMEOUT_S = 0.25
    _SUPPORTED_GESTURES = frozenset(
        {
            "open_palm",
            "fist",
            "thumbs_up",
            "point_up",
            "point_down",
            "point_left",
            "point_right",
            "l_shape_right",
            "l_shape_left",
        }
    )
    _GESTURE_COMMAND_MAP = {
        gesture_name: behavior.command for gesture_name, behavior in GESTURE_BEHAVIOR_CONFIG.items()
    }
    _INIT_LOGGED = False

    def __init__(self, config: AppConfig | None = None) -> None:
        self._config = config or AppConfig()
        # AppConfig.gesture_stability controls history length and gesture dominance.
        self.stability_frames = max(1, int(self._config.gesture_stability.stability_frames))
        self.dominance_frames = max(
            1,
            min(self.stability_frames, int(self._config.gesture_stability.dominance_frames)),
        )
        # AppConfig.gesture_thresholds controls confidence gating before commands are exposed.
        self.min_confidence = max(0.0, min(1.0, float(self._config.gesture_thresholds.default_min_confidence)))
        self.noise_confidence_floor = max(
            0.0,
            min(1.0, float(self._config.gesture_thresholds.noise_confidence_floor)),
        )
        # AppConfig.gesture_inference controls detector throughput and debug bypass behavior.
        self.max_num_hands = max(1, int(self._config.gesture_inference.max_num_hands))
        self.debug_bypass_stability = bool(self._config.gesture_inference.debug_bypass_stability)
        self.debug_bypass_min_confidence = max(
            0.0,
            min(1.0, float(self._config.gesture_inference.debug_bypass_min_confidence)),
        )
        self._history: Deque[str | None] = deque(maxlen=self.stability_frames)
        self._gesture_command_map = dict(self._GESTURE_COMMAND_MAP)
        self._enabled_gesture_commands = set(self._gesture_command_map.keys())
        self._fast_path_hits = 2
        self._max_reliable_distance_m = float(self._config.gesture_environment.max_reliable_distance_m)
        self._distance_compensation_enabled = bool(self._config.gesture_environment.distance_compensation_enabled)
        self._detector: Any | None = None
        self._recognizer: Any | None = None
        self._detector_available = False
        self._detector_status: DetectorStatus = "detector_unavailable"
        self._detector_error: str | None = None
        self._model_path = self._resolve_model_path()
        self._init_attempted = False
        self._detector_unavailable_logged = False
        self._recognition_condition = Condition()
        self._pending_recognition: dict[int, tuple[str | None, float | None]] = {}
        self._last_timestamp_ms = 0

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
            timestamp_ms = self._next_timestamp_ms()
            with self._recognition_condition:
                self._pending_recognition.pop(timestamp_ms, None)
            self._recognizer.recognize_async(mp_image, timestamp_ms)
            recognizer_label, raw_gesture, confidence = self._await_recognition_result(timestamp_ms)
            gesture_debug_log(
                "inference.process_ok",
                frame_shape=frame_shape,
                frame_dtype=frame_dtype,
                process_ok=True,
                recognition_source="recognizer",
                recognizer_label=recognizer_label,
                raw_gesture=raw_gesture,
                confidence=confidence,
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

        if raw_gesture is None:
            self._history.append(None)
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
                detector_available=self._detector_available,
                detector_status=self._detector_status,
            )
            return self._build_inference_result(
                raw_gesture=None,
                stable_gesture=None,
                confidence=None,
                command_name=None,
                queue_state="detecting",
                stable_hits=0,
                required_hits=self.dominance_frames,
                required_confidence=self.min_confidence,
            )

        if confidence is None or confidence < self.noise_confidence_floor:
            self._history.append(self._NOISE_MARKER)
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
                detector_available=self._detector_available,
                detector_status=self._detector_status,
            )
            return self._build_inference_result(
                raw_gesture=raw_gesture,
                stable_gesture=None,
                confidence=confidence,
                command_name=None,
                queue_state="low_confidence",
                stable_hits=0,
                required_hits=self.dominance_frames,
                required_confidence=self.min_confidence,
            )

        self._history.append(raw_gesture)
        stable_gesture, stable_hits = self._stabilize_gesture(with_count=True)
        command_name, queue_state, required_hits, required_confidence = self._resolve_command(
            raw_gesture,
            stable_gesture,
            stable_hits,
            confidence,
        )
        stable_gesture_out = None if queue_state == "low_confidence" else stable_gesture
        command_name_out = None if queue_state == "low_confidence" else command_name
        gesture_debug_log(
            "inference.recognizer_mapped",
            recognition_source="recognizer",
            recognizer_label=recognizer_label,
            mapped_gesture=raw_gesture,
            confidence=confidence,
            threshold=required_confidence,
            queue_state=queue_state,
            detector_available=self._detector_available,
            detector_status=self._detector_status,
        )
        gesture_debug_log(
            "inference.resolved",
            recognition_source="recognizer",
            recognizer_label=recognizer_label,
            mapped_gesture=raw_gesture,
            raw_gesture=raw_gesture,
            stable_gesture=stable_gesture_out,
            confidence=confidence,
            resolved_command=command_name_out,
            queue_state=queue_state,
            stable_hits=stable_hits,
            required_hits=required_hits,
            required_confidence=required_confidence,
            debug_bypass_stability=self.debug_bypass_stability,
            detector_available=self._detector_available,
            detector_status=self._detector_status,
        )

        return self._build_inference_result(
            raw_gesture=raw_gesture,
            stable_gesture=stable_gesture_out,
            confidence=confidence,
            command_name=command_name_out,
            queue_state=queue_state,
            stable_hits=stable_hits,
            required_hits=required_hits,
            required_confidence=required_confidence,
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
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision
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
            options = vision.GestureRecognizerOptions(
                base_options=python.BaseOptions(model_asset_path=str(model_path)),
                running_mode=vision.RunningMode.LIVE_STREAM,
                num_hands=self.max_num_hands,
                result_callback=self._on_recognition_result,
            )
            self._recognizer = vision.GestureRecognizer.create_from_options(options)
            self._detector = self._recognizer
            self._detector_available = True
            self._detector_status = "detector_ready"
            self._detector_error = None
            gesture_debug_log(
                "inference.detector_init_success",
                detector_available=self._detector_available,
                detector_status=self._detector_status,
                recognition_source="recognizer",
                dependencies_available=True,
                model_path=self._model_path,
                detector_type="GestureRecognizer",
            )
        except Exception as exc:
            self._set_detector_failure(
                status="detector_init_failed",
                error=_format_exception(exc) or "GestureRecognizer creation failed",
                dependencies_available=True,
            )

    def _empty_result(self, queue_state: str) -> GestureInferenceResult:
        return self._build_inference_result(
            raw_gesture=None,
            stable_gesture=None,
            confidence=None,
            command_name=None,
            queue_state=queue_state,
            stable_hits=0,
            required_hits=self.dominance_frames,
            required_confidence=self.min_confidence,
        )

    def _resolve_command(
        self,
        raw_gesture: str | None,
        stable_gesture: str | None,
        stable_hits: int,
        confidence: float | None,
    ) -> tuple[str | None, str, int, float]:
        if stable_gesture is None:
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

        required_hits = self.dominance_frames
        min_confidence = self._config.gesture_min_confidence(stable_gesture)

        if confidence is None:
            return None, "low_confidence", required_hits, min_confidence
        if self.debug_bypass_stability and confidence >= self.debug_bypass_min_confidence:
            return command_name, "debug_bypass", required_hits, min_confidence
        if confidence < min_confidence:
            return None, "low_confidence", required_hits, min_confidence
        if behavior.behavior_type == "safety":
            return command_name, "ready", 1, min_confidence
        if (
            behavior.behavior_type == "repeatable"
            and confidence >= self._config.gesture_fast_path_confidence(stable_gesture)
            and stable_hits >= self._fast_path_hits
        ):
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
        return str(project_root / "models" / "gesture_recognizer.task")

    def _next_timestamp_ms(self) -> int:
        timestamp_ms = int(monotonic() * 1000.0)
        if timestamp_ms <= self._last_timestamp_ms:
            timestamp_ms = self._last_timestamp_ms + 1
        self._last_timestamp_ms = timestamp_ms
        return timestamp_ms

    def _await_recognition_result(self, timestamp_ms: int) -> tuple[str | None, str | None, float | None]:
        deadline = monotonic() + self._RECOGNIZER_RESULT_TIMEOUT_S
        with self._recognition_condition:
            while timestamp_ms not in self._pending_recognition:
                remaining = deadline - monotonic()
                if remaining <= 0.0:
                    gesture_debug_log(
                        "inference.recognizer_timeout",
                        timestamp_ms=timestamp_ms,
                        timeout_s=self._RECOGNIZER_RESULT_TIMEOUT_S,
                        detector_available=self._detector_available,
                        detector_status=self._detector_status,
                    )
                    return None, None, None
                self._recognition_condition.wait(timeout=remaining)
            return self._pending_recognition.pop(timestamp_ms)

    def _on_recognition_result(self, result: Any, output_image: Any, timestamp_ms: int) -> None:
        recognizer_label: str | None = None
        gesture_name: str | None = None
        confidence: float | None = None
        try:
            gestures = getattr(result, "gestures", None)
            if gestures and len(gestures) > 0 and gestures[0]:
                top = gestures[0][0]
                recognizer_label = getattr(top, "category_name", None)
                gesture_name = self._map_recognizer_label(recognizer_label)
                score = getattr(top, "score", None)
                confidence = float(score) if score is not None else None
        except Exception as exc:
            gesture_debug_log(
                "inference.recognizer_callback_error",
                timestamp_ms=timestamp_ms,
                error=_format_exception(exc),
            )
            gesture_name = None
            confidence = None

        gesture_debug_log(
            "inference.recognizer_result",
            timestamp_ms=timestamp_ms,
            recognition_source="recognizer",
            recognizer_label=recognizer_label,
            mapped_gesture=gesture_name,
            raw_gesture=gesture_name,
            confidence=confidence,
        )
        with self._recognition_condition:
            self._pending_recognition[timestamp_ms] = (recognizer_label, gesture_name, confidence)
            self._recognition_condition.notify_all()

    def _map_recognizer_label(self, label: str | None) -> str | None:
        if not label:
            return None
        normalized = str(label).strip()
        mapping = {
            "Closed_Fist": "fist",
            "Open_Palm": "open_palm",
            "Pointing_Up": "point_up",
            "Thumb_Up": "thumbs_up",
            "Thumb_Down": "point_down",
            "Victory": "victory",
            "ILoveYou": "i_love_you",
        }
        mapped = mapping.get(normalized)
        if mapped not in self._SUPPORTED_GESTURES:
            return None
        return mapped

    def _build_inference_result(
        self,
        *,
        raw_gesture: str | None,
        stable_gesture: str | None,
        confidence: float | None,
        command_name: str | None,
        queue_state: str,
        stable_hits: int,
        required_hits: int,
        required_confidence: float,
    ) -> GestureInferenceResult:
        # Gesture labels now come exclusively from MediaPipe GestureRecognizer.
        # Legacy landmark-rule classification is intentionally disabled.
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
