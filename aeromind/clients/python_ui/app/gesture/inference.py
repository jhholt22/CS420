from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any

import cv2

try:
    import mediapipe as mp
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
except Exception:
    mp = None
    python = None
    vision = None


@dataclass
class GesturePrediction:
    raw_gesture: Optional[str]
    stable_gesture: Optional[str]
    confidence: float
    stable_for_ms: int
    changed: bool


class GestureInference:
    """
    MediaPipe Tasks based hand landmark inference with temporal stability.
    Uses the new HandLandmarker API instead of the removed mp.solutions.hands API.
    """

    def __init__(
        self,
        stability_ms: int = 800,
        model_path: Optional[str] = None,
        num_hands: int = 1,
        min_hand_detection_confidence: float = 0.5,
        min_hand_presence_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        self._stability_ms = stability_ms

        self._last_raw_gesture: Optional[str] = None
        self._raw_since: float = 0.0

        self._stable_gesture: Optional[str] = None
        self._stable_since: float = 0.0

        self._landmarker = None
        self._frame_index = 0

        if mp is None or python is None or vision is None:
            return

        if model_path is None:
            model_path = str(Path("models") / "hand_landmarker.task")

        model_file = Path(model_path)
        if not model_file.exists():
            print(
                f"[Gesture] MediaPipe model missing at {model_file}; gesture detection disabled",
                flush=True,
            )
            return

        base_options = python.BaseOptions(model_asset_path=str(model_file))
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_hands=num_hands,
            min_hand_detection_confidence=min_hand_detection_confidence,
            min_hand_presence_confidence=min_hand_presence_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

        try:
            self._landmarker = vision.HandLandmarker.create_from_options(options)
        except Exception as exc:
            print(f"[Gesture] Failed to initialize MediaPipe hand landmarker: {exc}", flush=True)
            self._landmarker = None

    def close(self) -> None:
        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None

    def process(self, frame: Optional[Any] = None) -> GesturePrediction:
        now = time.monotonic()
        raw_gesture, confidence = self._predict_raw(frame)

        changed = raw_gesture != self._last_raw_gesture
        if changed:
            self._last_raw_gesture = raw_gesture
            self._raw_since = now

        stable_for_ms = 0
        stable_candidate = None

        if raw_gesture:
            stable_for_ms = int((now - self._raw_since) * 1000)
            if stable_for_ms >= self._stability_ms:
                stable_candidate = raw_gesture

        if stable_candidate != self._stable_gesture:
            self._stable_gesture = stable_candidate
            self._stable_since = now if stable_candidate else 0.0

        return GesturePrediction(
            raw_gesture=raw_gesture,
            stable_gesture=self._stable_gesture,
            confidence=confidence,
            stable_for_ms=stable_for_ms,
            changed=changed,
        )

    def _predict_raw(self, frame: Optional[Any]) -> tuple[Optional[str], float]:
        if frame is None or self._landmarker is None or mp is None:
            return None, 0.0

        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

            self._frame_index += 1
            timestamp_ms = int(time.monotonic() * 1000)

            result = self._landmarker.detect_for_video(mp_image, timestamp_ms)

            if not result.hand_landmarks:
                return None, 0.0

            landmarks = result.hand_landmarks[0]

            handedness_score = 0.5
            if result.handedness and len(result.handedness) > 0 and len(result.handedness[0]) > 0:
                handedness_score = float(result.handedness[0][0].score)

            gesture, confidence = self._classify_landmarks(landmarks, handedness_score)
            return gesture, confidence

        except Exception:
            return None, 0.0

    def _classify_landmarks(
        self,
        landmarks: list[Any],
        handedness_score: float,
    ) -> tuple[Optional[str], float]:
        # HandLandmarker returns 21 landmarks in the standard MediaPipe hand order.
        WRIST = 0
        THUMB_CMC = 1
        THUMB_MCP = 2
        THUMB_IP = 3
        THUMB_TIP = 4
        INDEX_FINGER_MCP = 5
        INDEX_FINGER_PIP = 6
        INDEX_FINGER_DIP = 7
        INDEX_FINGER_TIP = 8
        MIDDLE_FINGER_MCP = 9
        MIDDLE_FINGER_PIP = 10
        MIDDLE_FINGER_DIP = 11
        MIDDLE_FINGER_TIP = 12
        RING_FINGER_MCP = 13
        RING_FINGER_PIP = 14
        RING_FINGER_DIP = 15
        RING_FINGER_TIP = 16
        PINKY_MCP = 17
        PINKY_PIP = 18
        PINKY_DIP = 19
        PINKY_TIP = 20

        tip_ids = (
            THUMB_TIP,
            INDEX_FINGER_TIP,
            MIDDLE_FINGER_TIP,
            RING_FINGER_TIP,
            PINKY_TIP,
        )
        pip_ids = (
            THUMB_IP,
            INDEX_FINGER_PIP,
            MIDDLE_FINGER_PIP,
            RING_FINGER_PIP,
            PINKY_PIP,
        )
        mcp_ids = (
            THUMB_MCP,
            INDEX_FINGER_MCP,
            MIDDLE_FINGER_MCP,
            RING_FINGER_MCP,
            PINKY_MCP,
        )

        finger_open = [
            self._distance_2d(landmarks[tip], landmarks[mcp]) >
            self._distance_2d(landmarks[pip], landmarks[mcp]) * 1.15
            for tip, pip, mcp in zip(tip_ids, pip_ids, mcp_ids)
        ]

        thumb_open, index_open, middle_open, ring_open, pinky_open = finger_open
        open_count = sum(1 for is_open in finger_open if is_open)

        if open_count >= 4:
            return "PALM", max(0.7, handedness_score)

        if open_count == 0:
            return "FIST", max(0.7, handedness_score)

        wrist = landmarks[WRIST]
        thumb_tip = landmarks[THUMB_TIP]
        index_tip = landmarks[INDEX_FINGER_TIP]
        index_mcp = landmarks[INDEX_FINGER_MCP]

        if thumb_open and not any((index_open, middle_open, ring_open, pinky_open)):
            vertical_delta = wrist.y - thumb_tip.y
            if abs(vertical_delta) >= 0.22:
                return ("THUMB_UP", 0.8) if vertical_delta > 0 else ("THUMB_DOWN", 0.8)

        if index_open and not any((thumb_open, middle_open, ring_open, pinky_open)):
            horizontal_delta = index_tip.x - index_mcp.x
            # Keep pointing more conservative to avoid noisy lateral commands.
            if abs(horizontal_delta) >= 0.18:
                return ("POINT_RIGHT", 0.8) if horizontal_delta > 0 else ("POINT_LEFT", 0.8)

        return None, 0.0

    @staticmethod
    def _distance_2d(a: Any, b: Any) -> float:
        return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5
