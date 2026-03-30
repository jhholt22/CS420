from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional, Any


@dataclass
class GesturePrediction:
    raw_gesture: Optional[str]
    stable_gesture: Optional[str]
    confidence: float
    stable_for_ms: int
    changed: bool


class GestureInference:
    """
    Stub inference layer.

    Right now:
    - can use a simulation provider
    - keeps basic temporal stability
    - returns stable gesture only after it survives the threshold

    Later:
    - replace _predict_raw() with MediaPipe / model inference
    - keep the same external API so the UI does not care
    """

    def __init__(
        self,
        simulation_provider: Optional[Callable[[], Optional[str]]] = None,
        stability_ms: int = 800,
    ) -> None:
        self._simulation_provider = simulation_provider
        self._stability_ms = stability_ms

        self._last_raw_gesture: Optional[str] = None
        self._raw_since: float = 0.0

        self._stable_gesture: Optional[str] = None
        self._stable_since: float = 0.0

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
        """
        Current stub:
        - ignore frame
        - read a simulated gesture from the UI/provider

        Later:
        - inspect frame
        - run MediaPipe or model
        - return (gesture_label, confidence)
        """
        if self._simulation_provider is None:
            return None, 0.0

        gesture = self._simulation_provider()
        if not gesture or gesture.upper() == "NONE":
            return None, 0.0

        return gesture.strip().upper(), 1.0