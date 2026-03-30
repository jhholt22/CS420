from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SafetyDecision:
    allowed: bool
    command: str
    reason: str


class SafetyLayer:
    def __init__(self, conf_threshold: float, stable_window_ms: int, command_cooldown_ms: int):
        self.conf_threshold = conf_threshold
        self.stable_window_ms = stable_window_ms
        self.command_cooldown_ms = command_cooldown_ms
        self._last_command_ts = 0

    def decide(
        self,
        ts_ms: int,
        gesture: str,
        confidence: float,
        stable_ms: int,
        command: str,
    ) -> SafetyDecision:
        if command == "none":
            return SafetyDecision(False, "none", "no_command")

        if confidence < self.conf_threshold:
            return SafetyDecision(False, command, "low_confidence")

        if stable_ms < self.stable_window_ms:
            return SafetyDecision(False, command, "not_stable")

        if ts_ms - self._last_command_ts < self.command_cooldown_ms:
            return SafetyDecision(False, command, "cooldown")

        self._last_command_ts = ts_ms
        return SafetyDecision(True, command, "allowed")