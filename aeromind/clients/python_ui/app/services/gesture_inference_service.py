from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Deque

import cv2
from app.utils.logging_utils import gesture_debug_log

try:
    import mediapipe as mp
except Exception:  # pragma: no cover - optional dependency
    mp = None


@dataclass(slots=True)
class GestureInferenceResult:
    raw_gesture: str | None
    stable_gesture: str | None
    confidence: float | None
    command_name: str | None
    queue_state: str
    detector_available: bool


class GestureInferenceService:
    _NOISE_MARKER = "__noise__"
    _ONE_SHOT_COMMANDS = {"takeoff", "land", "emergency"}
    _REPEATABLE_COMMANDS = {"up", "down", "forward"}
    _NEUTRAL_GESTURES = {"open_palm"}
    _DEFAULT_MIN_CONFIDENCE = 0.72
    _GESTURE_COMMAND_MAP = {
        "thumbs_up": "takeoff",
        "fist": "land",
        "thumbs_down": "down",
        "point_up": "forward",
    }

    def __init__(
        self,
        stability_frames: int = 6,
        dominance_frames: int = 4,
        min_confidence: float = _DEFAULT_MIN_CONFIDENCE,
        noise_confidence_floor: float = 0.60,
        max_num_hands: int = 1,
    ) -> None:
        self.stability_frames = max(1, int(stability_frames))
        self.dominance_frames = max(1, min(self.stability_frames, int(dominance_frames)))
        self.min_confidence = max(0.0, min(1.0, float(min_confidence)))
        self.noise_confidence_floor = max(0.0, min(1.0, float(noise_confidence_floor)))
        self.max_num_hands = max(1, int(max_num_hands))
        self._history: Deque[str | None] = deque(maxlen=self.stability_frames)
        self._gesture_command_map = dict(self._GESTURE_COMMAND_MAP)
        self._enabled_gesture_commands = {
            "thumbs_up",
            "fist",
            "thumbs_down",
            "point_up",
        }
        self._gesture_safety_rules = {
            "thumbs_up": {"min_confidence": 0.92, "required_hits": self.stability_frames},
            "fist": {"min_confidence": 0.93, "required_hits": self.stability_frames},
            "thumbs_down": {"min_confidence": 0.84, "required_hits": self.dominance_frames},
            "point_up": {"min_confidence": 0.86, "required_hits": self.dominance_frames},
        }
        self._mp_hands = None
        self._hands = None
        self._detector_available = False
        self._initialize_detector()

    def process_frame(self, frame: Any) -> GestureInferenceResult:
        if frame is None:
            gesture_debug_log(
                "inference.empty_frame",
                detector_available=self._detector_available,
                queue_state="idle",
            )
            return self._empty_result("idle")

        if not self._detector_available or self._hands is None:
            gesture_debug_log(
                "inference.detector_unavailable",
                detector_available=self._detector_available,
                queue_state="detector_unavailable",
            )
            return self._empty_result("detector_unavailable")

        try:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self._hands.process(rgb_frame)
        except Exception:
            gesture_debug_log(
                "inference.detector_error",
                detector_available=self._detector_available,
                queue_state="detector_unavailable",
            )
            return self._empty_result("detector_unavailable")

        hand_landmarks, handedness = self._extract_hand_landmarks(results)
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
            )
            return GestureInferenceResult(
                raw_gesture=None,
                stable_gesture=None,
                confidence=None,
                command_name=None,
                queue_state="detecting",
                detector_available=self._detector_available,
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
            )
            return GestureInferenceResult(
                raw_gesture=None,
                stable_gesture=stable_gesture,
                confidence=confidence,
                command_name=None,
                queue_state="detecting",
                detector_available=self._detector_available,
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
            )
            return GestureInferenceResult(
                raw_gesture=raw_gesture,
                stable_gesture=stable_gesture,
                confidence=confidence,
                command_name=None,
                queue_state="low_confidence",
                detector_available=self._detector_available,
            )

        self._history.append(raw_gesture)
        stable_gesture, stable_hits = self._stabilize_gesture(with_count=True)
        command_name, queue_state = self._resolve_command(stable_gesture, stable_hits, confidence)
        gesture_debug_log(
            "inference.resolved",
            raw_gesture=raw_gesture,
            stable_gesture=stable_gesture,
            confidence=confidence,
            resolved_command=command_name,
            queue_state=queue_state,
            stable_hits=stable_hits,
            detector_available=self._detector_available,
        )

        return GestureInferenceResult(
            raw_gesture=raw_gesture,
            stable_gesture=stable_gesture,
            confidence=confidence,
            command_name=command_name,
            queue_state=queue_state,
            detector_available=self._detector_available,
        )

    def reset(self) -> None:
        self._history.clear()

    def is_detector_available(self) -> bool:
        return self._detector_available

    def get_enabled_gesture_commands(self) -> dict[str, str]:
        return {
            gesture_name: command_name
            for gesture_name, command_name in self._gesture_command_map.items()
            if gesture_name in self._enabled_gesture_commands
        }

    def _initialize_detector(self) -> None:
        if mp is None:
            self._detector_available = False
            return

        try:
            self._mp_hands = mp.solutions.hands
            self._hands = self._mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=self.max_num_hands,
                model_complexity=0,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            self._detector_available = True
        except Exception:
            self._mp_hands = None
            self._hands = None
            self._detector_available = False

    def _empty_result(self, queue_state: str) -> GestureInferenceResult:
        return GestureInferenceResult(
            raw_gesture=None,
            stable_gesture=None,
            confidence=None,
            command_name=None,
            queue_state=queue_state,
            detector_available=self._detector_available,
        )

    def _extract_hand_landmarks(self, results: Any) -> tuple[Any | None, str | None]:
        if results is None:
            return None, None

        multi_hand_landmarks = getattr(results, "multi_hand_landmarks", None)
        if not multi_hand_landmarks:
            return None, None

        handedness_label: str | None = None
        multi_handedness = getattr(results, "multi_handedness", None)
        if multi_handedness:
            try:
                handedness_label = multi_handedness[0].classification[0].label
            except Exception:
                handedness_label = None

        return multi_hand_landmarks[0], handedness_label

    def _classify_landmarks(self, landmarks: Any, handedness: str | None) -> tuple[str | None, float | None]:
        finger_states = self._finger_states(landmarks, handedness)
        thumb_vertical = self._thumb_vertical_direction(landmarks)

        extended_count = sum(bool(value) for value in finger_states.values())
        other_folded = not finger_states["index"] and not finger_states["middle"] and not finger_states["ring"] and not finger_states["pinky"]
        index_above_middle = landmarks.landmark[8].y < landmarks.landmark[12].y - 0.03

        if finger_states["thumb"] and all(finger_states[name] for name in ("index", "middle", "ring", "pinky")):
            return "open_palm", 0.94

        if extended_count == 0:
            return "fist", 0.94

        if (
            finger_states["index"]
            and not finger_states["middle"]
            and not finger_states["ring"]
            and not finger_states["pinky"]
            and not finger_states["thumb"]
            and index_above_middle
        ):
            return "point_up", 0.86

        if finger_states["thumb"] and other_folded:
            if thumb_vertical == "up":
                return "thumbs_up", 0.88
            if thumb_vertical == "down":
                return "thumbs_down", 0.88

        if extended_count >= 4:
            return "open_palm", 0.68

        if extended_count <= 1:
            return "fist", 0.66

        return None, None

    def _finger_states(self, landmarks: Any, handedness: str | None) -> dict[str, bool]:
        points = landmarks.landmark
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

    def _thumb_vertical_direction(self, landmarks: Any) -> str | None:
        points = landmarks.landmark
        thumb_tip_y = points[4].y
        thumb_ip_y = points[3].y
        thumb_mcp_y = points[2].y
        wrist_y = points[0].y

        if thumb_tip_y < thumb_ip_y < thumb_mcp_y and thumb_tip_y < wrist_y:
            return "up"
        if thumb_tip_y > thumb_ip_y > thumb_mcp_y and thumb_tip_y > wrist_y:
            return "down"
        return None

    def _resolve_command(
        self,
        stable_gesture: str | None,
        stable_hits: int,
        confidence: float | None,
    ) -> tuple[str | None, str]:
        if stable_gesture is None:
            return None, "stabilizing"

        if confidence is None or confidence < self.min_confidence:
            return None, "low_confidence"

        if stable_gesture in self._NEUTRAL_GESTURES:
            return None, "neutral"

        if stable_gesture not in self._enabled_gesture_commands:
            return None, "disabled"

        command_name = self._gesture_command_map.get(stable_gesture)
        if not command_name:
            return None, "stabilizing"

        safety_rule = self._gesture_safety_rules.get(stable_gesture, {})
        default_hits = self.stability_frames if command_name in self._ONE_SHOT_COMMANDS else self.dominance_frames
        default_confidence = self.min_confidence + (0.14 if command_name in self._ONE_SHOT_COMMANDS else 0.10)
        min_confidence = float(safety_rule.get("min_confidence", default_confidence))
        required_hits = int(safety_rule.get("required_hits", default_hits))

        if confidence < min_confidence:
            return None, "guarded"
        if stable_hits < required_hits:
            return None, "stabilizing"
        return command_name, "ready"

    @classmethod
    def get_threshold_for_gesture(cls, stable_gesture: str | None) -> float:
        if not stable_gesture:
            return cls._DEFAULT_MIN_CONFIDENCE

        if stable_gesture in cls._NEUTRAL_GESTURES:
            return cls._DEFAULT_MIN_CONFIDENCE

        safety_rule = {
            "thumbs_up": {"min_confidence": 0.92},
            "fist": {"min_confidence": 0.93},
            "thumbs_down": {"min_confidence": 0.84},
            "point_up": {"min_confidence": 0.86},
        }.get(stable_gesture, {})
        command_name = cls._GESTURE_COMMAND_MAP.get(stable_gesture)
        default_confidence = cls._DEFAULT_MIN_CONFIDENCE
        if command_name in cls._ONE_SHOT_COMMANDS:
            default_confidence += 0.14
        elif command_name in cls._REPEATABLE_COMMANDS:
            default_confidence += 0.10
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
