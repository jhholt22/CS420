from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class GesturePrediction:
    gesture: str
    confidence: float


class GestureModel:
    """
    Placeholder gesture model.

    This keeps the architecture clean while you rebuild.
    Later you can plug in MediaPipe / custom model / OpenCV pipeline here.
    """

    def __init__(self) -> None:
        self.ready = True

    def predict(self, frame: Any) -> GesturePrediction:
        # Temporary stub
        return GesturePrediction(gesture="none", confidence=0.0)