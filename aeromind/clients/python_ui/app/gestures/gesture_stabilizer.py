from __future__ import annotations

from collections import deque
from typing import Deque


class GestureStabilizer:
    def __init__(self, *, stability_frames: int, dominance_frames: int, noise_marker: str = "__noise__") -> None:
        self.stability_frames = max(1, int(stability_frames))
        self.dominance_frames = max(1, min(self.stability_frames, int(dominance_frames)))
        self.noise_marker = noise_marker
        self._history: Deque[str | None] = deque(maxlen=self.stability_frames)

    def reset(self) -> None:
        self._history.clear()

    def observe(self, gesture_name: str | None) -> None:
        self._history.append(gesture_name)

    def observe_noise(self) -> None:
        self._history.append(self.noise_marker)

    def stabilize(self) -> tuple[str | None, int]:
        if len(self._history) < self.dominance_frames:
            return None, 0

        counts: dict[str, int] = {}
        for item in self._history:
            if item is None or item == self.noise_marker:
                continue
            counts[item] = counts.get(item, 0) + 1

        if not counts:
            return None, 0

        stable_gesture, stable_hits = max(counts.items(), key=lambda entry: entry[1])
        if stable_hits < self.dominance_frames:
            return None, stable_hits
        return stable_gesture, stable_hits
