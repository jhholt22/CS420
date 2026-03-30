from dataclasses import dataclass


@dataclass
class GesturePrediction:
    gesture: str
    confidence: float


class GestureModel:
    def __init__(self):
        pass

    def predict(self, frame) -> GesturePrediction:
        return GesturePrediction("none", 0.0)
