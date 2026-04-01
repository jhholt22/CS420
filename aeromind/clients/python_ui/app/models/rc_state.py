from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RcState:
    lr: int = 0
    fb: int = 0
    ud: int = 0
    yaw: int = 0

    def clamp(self) -> RcState:
        self.lr = self._clamp_value(self.lr)
        self.fb = self._clamp_value(self.fb)
        self.ud = self._clamp_value(self.ud)
        self.yaw = self._clamp_value(self.yaw)
        return self

    def apply_deadzone(self, deadzone: int) -> RcState:
        threshold = max(0, int(deadzone))
        if abs(self.lr) < threshold:
            self.lr = 0
        if abs(self.fb) < threshold:
            self.fb = 0
        if abs(self.ud) < threshold:
            self.ud = 0
        if abs(self.yaw) < threshold:
            self.yaw = 0
        return self

    def is_neutral(self) -> bool:
        return self.lr == 0 and self.fb == 0 and self.ud == 0 and self.yaw == 0

    def is_same_as(self, other: RcState) -> bool:
        return (
            self.lr == other.lr
            and self.fb == other.fb
            and self.ud == other.ud
            and self.yaw == other.yaw
        )

    def copy(self) -> RcState:
        return RcState(lr=self.lr, fb=self.fb, ud=self.ud, yaw=self.yaw)

    def to_payload(self) -> dict[str, int]:
        self.clamp()
        return {
            "lr": self.lr,
            "fb": self.fb,
            "ud": self.ud,
            "yaw": self.yaw,
        }

    @staticmethod
    def _clamp_value(value: int) -> int:
        return max(-100, min(100, int(value)))
