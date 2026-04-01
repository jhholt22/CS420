from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Deque

import cv2

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
    def __init__(
        self,
        stability_frames: int = 5,
        min_confidence: float = 0.7,
        max_num_hands: int = 1,
    ) -> None:
        self.stability_frames = max(1, int(stability_frames))
        self.min_confidence = max(0.0, min(1.0, float(min_confidence)))
        self.max_num_hands = max(1, int(max_num_hands))
        self._history: Deque[str | None] = deque(maxlen=self.stability_frames)
        self._gesture_command_map = {
            "open_palm": "takeoff",
            "fist": "land",
            "thumbs_up": "up",
            "thumbs_down": "down",
            "point_up": "forward",
        }
        self._mp_hands = None
        self._hands = None
        self._detector_available = False
        self._initialize_detector()

    def process_frame(self, frame: Any) -> GestureInferenceResult:
        if frame is None:
            return self._empty_result("idle")

        if not self._detector_available or self._hands is None:
            return self._empty_result("detector_unavailable")

        try:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self._hands.process(rgb_frame)
        except Exception:
            return self._empty_result("detector_unavailable")

        hand_landmarks, handedness = self._extract_hand_landmarks(results)
        if hand_landmarks is None:
            self._history.append(None)
            return GestureInferenceResult(
                raw_gesture=None,
                stable_gesture=None,
                confidence=None,
                command_name=None,
                queue_state="detecting",
                detector_available=self._detector_available,
            )

        raw_gesture, confidence = self._classify_landmarks(hand_landmarks, handedness)
        stable_gesture = self._stabilize_gesture(raw_gesture)
        command_name = None
        queue_state = "stabilizing"

        if raw_gesture is None:
            queue_state = "detecting"
        elif stable_gesture and confidence is not None and confidence >= self.min_confidence:
            command_name = self._gesture_command_map.get(stable_gesture)
            queue_state = "ready" if command_name else "stabilizing"

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

        if finger_states["thumb"] and all(finger_states[name] for name in ("index", "middle", "ring", "pinky")):
            return "open_palm", 0.9

        if extended_count == 0:
            return "fist", 0.9

        if (
            finger_states["index"]
            and not finger_states["middle"]
            and not finger_states["ring"]
            and not finger_states["pinky"]
            and not finger_states["thumb"]
        ):
            return "point_up", 0.84

        if finger_states["thumb"] and other_folded:
            if thumb_vertical == "up":
                return "thumbs_up", 0.86
            if thumb_vertical == "down":
                return "thumbs_down", 0.86

        if extended_count >= 4:
            return "open_palm", 0.74

        if extended_count <= 1:
            return "fist", 0.72

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

    def _stabilize_gesture(self, raw_gesture: str | None) -> str | None:
        self._history.append(raw_gesture)
        if len(self._history) < self.stability_frames:
            return None

        first = self._history[0]
        if first is None:
            return None
        if all(item == first for item in self._history):
            return first
        return None
