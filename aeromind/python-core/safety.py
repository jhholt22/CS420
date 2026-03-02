from dataclasses import dataclass

@dataclass
class SafetyDecision:
    allowed: bool
    reason: str  # none | low_confidence | not_stable | cooldown | safety_lock
    command: str

class SafetyLayer:
    def __init__(self, conf_threshold: float, stable_window_ms: int, cooldown_ms: int):
        self.conf_threshold = conf_threshold
        self.stable_window_ms = stable_window_ms
        self.cooldown_ms = cooldown_ms
        self._last_command_ts = -10**18

    def decide(self, ts_ms: int, gesture: str, confidence: float, stable_ms: int, command: str) -> SafetyDecision:
        # emergency always wins
        if gesture == "emergency_stop":
            self._last_command_ts = ts_ms
            return SafetyDecision(True, "none", "emergency")

        if command == "none":
            return SafetyDecision(False, "none", "none")

        if confidence < self.conf_threshold:
            return SafetyDecision(False, "low_confidence", "none")

        if stable_ms < self.stable_window_ms:
            return SafetyDecision(False, "not_stable", "none")

        if ts_ms - self._last_command_ts < self.cooldown_ms:
            return SafetyDecision(False, "cooldown", "none")

        self._last_command_ts = ts_ms
        return SafetyDecision(True, "none", command)
