from dataclasses import dataclass

@dataclass
class GesturePrediction:
    gesture: str          # label
    confidence: float     # 0..1

class GestureModel:
    def __init__(self):
        # init mediapipe etc later
        pass

    def predict(self, frame) -> GesturePrediction:
        # TODO: return ("none", 0.0) if no hand
        return GesturePrediction("none", 0.0)
