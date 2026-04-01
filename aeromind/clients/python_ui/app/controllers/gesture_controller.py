from __future__ import annotations

from time import monotonic

from app.services.gesture_inference_service import GestureInferenceResult


class GestureController:
    """Tracks gesture state, debug values, and conservative dispatch cooldown."""

    def __init__(self, cooldown_ms: int = 1200) -> None:
        self._enabled = False
        self._cooldown_ms = max(0, int(cooldown_ms))
        self.reset()

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False
        self.reset()

    def toggle(self) -> bool:
        if self._enabled:
            self.disable()
        else:
            self.enable()
        return self._enabled

    def is_enabled(self) -> bool:
        return self._enabled

    def reset(self) -> None:
        self._raw_gesture = "-"
        self._stable_gesture = "-"
        self._last_command = "-"
        self._queue_state = "idle"
        self._confidence: float | None = None
        self._pending_command: str | None = None
        self._detector_available = False
        self._active_ready_command: str | None = None
        self._last_ready_command: str | None = None
        self._last_stable_gesture_name: str | None = None
        self._last_dispatched_command: str | None = None
        self._last_dispatched_at = 0.0

    def update_from_result(self, result: GestureInferenceResult) -> dict[str, str | float | bool | None]:
        if not self._enabled:
            self.reset()
            return self.get_debug_state()

        self._raw_gesture = result.raw_gesture or "-"
        self._stable_gesture = result.stable_gesture or "-"
        self._confidence = result.confidence if result.confidence is not None else None
        self._pending_command = result.command_name
        self._queue_state = result.queue_state or "idle"
        self._detector_available = result.detector_available

        if not self._detector_available:
            self._pending_command = None
            self._active_ready_command = None
            self._last_ready_command = None
            self._last_stable_gesture_name = None
            if self._queue_state == "idle":
                self._queue_state = "detector_unavailable"
            return self.get_debug_state()

        current_stable_gesture = result.stable_gesture
        if current_stable_gesture is None or current_stable_gesture != self._last_stable_gesture_name:
            self._active_ready_command = None
            self._last_ready_command = None
        self._last_stable_gesture_name = current_stable_gesture

        return self.get_debug_state()

    def should_dispatch_command(self, command_name: str | None) -> bool:
        if not self._enabled or not self._detector_available or not command_name:
            return False

        if self._last_ready_command != command_name:
            self._active_ready_command = None
        self._last_ready_command = command_name

        if self._active_ready_command == command_name:
            self._queue_state = "holding"
            return False

        now = monotonic()
        elapsed_ms = (now - self._last_dispatched_at) * 1000.0
        if self._last_dispatched_command == command_name and elapsed_ms < self._cooldown_ms:
            self._active_ready_command = command_name
            self._queue_state = "cooldown"
            return False

        self._active_ready_command = command_name
        self._queue_state = "dispatch"
        return True

    def mark_command_dispatched(self, command_name: str) -> None:
        self._last_command = command_name
        self._last_dispatched_command = command_name
        self._last_dispatched_at = monotonic()
        self._active_ready_command = command_name
        self._last_ready_command = command_name
        self._queue_state = "sent"
        self._pending_command = None

    def get_debug_state(self) -> dict[str, str | float | bool | None]:
        return {
            "gesture": "ON" if self._enabled else "OFF",
            "raw": self._raw_gesture,
            "stable": self._stable_gesture,
            "last_command": self._last_command,
            "queue_state": self._queue_state,
            "confidence": self._confidence,
            "pending_command": self._pending_command,
            "detector_available": self._detector_available,
        }
