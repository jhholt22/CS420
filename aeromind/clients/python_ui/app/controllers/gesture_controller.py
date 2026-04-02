from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

from app.services.gesture_inference_service import GestureInferenceResult, GestureInferenceService
from app.utils.logging_utils import gesture_debug_log


@dataclass(slots=True)
class GestureDispatchDecision:
    command_name: str | None
    dispatch_allowed: bool
    block_reason: str
    debug_state: dict[str, str | float | bool | None]


class GestureController:
    """Gesture gating with separate rules for one-shot and repeatable commands."""

    ONE_SHOT_COMMANDS = {"takeoff", "land", "emergency"}
    REPEATABLE_COMMANDS = {"up", "down", "forward"}

    def __init__(
        self,
        oneshot_cooldown_ms: int = 1800,
        repeat_cooldown_ms: int = 700,
        release_timeout_ms: int = 250,
    ) -> None:
        self._enabled = False
        self._oneshot_cooldown_ms = max(0, int(oneshot_cooldown_ms))
        self._repeat_cooldown_ms = max(0, int(repeat_cooldown_ms))
        self._release_timeout_ms = max(0, int(release_timeout_ms))
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

        self._last_stable_gesture_name: str | None = None
        self._stable_since = 0.0

        self._armed_oneshot_command: str | None = None
        self._last_dispatched_command: str | None = None
        self._last_dispatched_at = 0.0
        self._last_seen_stable_at = 0.0

    def update_from_result(self, result: GestureInferenceResult) -> dict[str, str | float | bool | None]:
        if not self._enabled:
            self.reset()
            gesture_debug_log(
                "controller.disabled",
                raw_gesture=result.raw_gesture,
                stable_gesture=result.stable_gesture,
                confidence=result.confidence,
                resolved_command=result.command_name,
                queue_state="gesture_off",
                detector_available=result.detector_available,
            )
            return self.get_debug_state()

        self._raw_gesture = result.raw_gesture or "-"
        self._stable_gesture = result.stable_gesture or "-"
        self._confidence = result.confidence
        self._pending_command = result.command_name
        self._queue_state = result.queue_state or "idle"
        self._detector_available = result.detector_available

        now = monotonic()

        if not self._detector_available:
            self._pending_command = None
            self._last_stable_gesture_name = None
            self._stable_since = 0.0
            self._armed_oneshot_command = None
            if self._queue_state == "idle":
                self._queue_state = "detector_unavailable"
            gesture_debug_log(
                "controller.no_detector",
                raw_gesture=self._raw_gesture,
                stable_gesture=self._stable_gesture,
                confidence=self._confidence,
                resolved_command=self._pending_command,
                queue_state=self._queue_state,
                detector_available=self._detector_available,
            )
            return self.get_debug_state()

        current_stable = result.stable_gesture

        if current_stable:
            self._last_seen_stable_at = now

        if current_stable != self._last_stable_gesture_name:
            self._stable_since = now if current_stable else 0.0

            # re-arm oneshot only when stable gesture actually changes away
            if self._last_stable_gesture_name and current_stable != self._last_stable_gesture_name:
                self._armed_oneshot_command = None

        # if gesture disappears long enough, re-arm oneshot
        if not current_stable and self._last_seen_stable_at > 0:
            gap_ms = (now - self._last_seen_stable_at) * 1000.0
            if gap_ms >= self._release_timeout_ms:
                self._armed_oneshot_command = None

        self._last_stable_gesture_name = current_stable
        gesture_debug_log(
            "controller.updated",
            raw_gesture=self._raw_gesture,
            stable_gesture=self._stable_gesture,
            confidence=self._confidence,
            resolved_command=self._pending_command,
            queue_state=self._queue_state,
            detector_available=self._detector_available,
        )
        return self.get_debug_state()

    def evaluate_result(self, result: GestureInferenceResult) -> GestureDispatchDecision:
        debug_state = self.update_from_result(result)
        command_name = result.command_name
        dispatch_allowed = self.should_dispatch_command(command_name)
        block_reason = "-" if dispatch_allowed else self.normalize_block_reason(command_name)
        return GestureDispatchDecision(
            command_name=command_name,
            dispatch_allowed=dispatch_allowed,
            block_reason=block_reason,
            debug_state=debug_state,
        )

    def should_dispatch_command(self, command_name: str | None) -> bool:
        if not self._enabled or not self._detector_available or not command_name:
            blocked_state = (
                "gesture_off"
                if not self._enabled
                else "detector_unavailable"
                if not self._detector_available
                else self._queue_state or "no_command"
            )
            gesture_debug_log(
                "controller.dispatch_blocked",
                raw_gesture=self._raw_gesture,
                stable_gesture=self._stable_gesture,
                confidence=self._confidence,
                resolved_command=command_name,
                queue_state=blocked_state,
                detector_available=self._detector_available,
            )
            return False

        now = monotonic()
        elapsed_ms = (now - self._last_dispatched_at) * 1000.0

        if command_name in self.ONE_SHOT_COMMANDS:
            if self._armed_oneshot_command == command_name:
                self._queue_state = "holding"
                gesture_debug_log(
                    "controller.dispatch_blocked",
                    raw_gesture=self._raw_gesture,
                    stable_gesture=self._stable_gesture,
                    confidence=self._confidence,
                    resolved_command=command_name,
                    queue_state=self._queue_state,
                    detector_available=self._detector_available,
                )
                return False

            if self._last_dispatched_command == command_name and elapsed_ms < self._oneshot_cooldown_ms:
                self._queue_state = "cooldown"
                gesture_debug_log(
                    "controller.dispatch_blocked",
                    raw_gesture=self._raw_gesture,
                    stable_gesture=self._stable_gesture,
                    confidence=self._confidence,
                    resolved_command=command_name,
                    queue_state=self._queue_state,
                    detector_available=self._detector_available,
                )
                return False

            self._queue_state = "dispatch"
            gesture_debug_log(
                "controller.dispatch_ready",
                raw_gesture=self._raw_gesture,
                stable_gesture=self._stable_gesture,
                confidence=self._confidence,
                resolved_command=command_name,
                queue_state=self._queue_state,
                detector_available=self._detector_available,
            )
            return True

        if command_name in self.REPEATABLE_COMMANDS:
            if self._last_dispatched_command == command_name and elapsed_ms < self._repeat_cooldown_ms:
                self._queue_state = "cooldown"
                gesture_debug_log(
                    "controller.dispatch_blocked",
                    raw_gesture=self._raw_gesture,
                    stable_gesture=self._stable_gesture,
                    confidence=self._confidence,
                    resolved_command=command_name,
                    queue_state=self._queue_state,
                    detector_available=self._detector_available,
                )
                return False

            self._queue_state = "dispatch"
            gesture_debug_log(
                "controller.dispatch_ready",
                raw_gesture=self._raw_gesture,
                stable_gesture=self._stable_gesture,
                confidence=self._confidence,
                resolved_command=command_name,
                queue_state=self._queue_state,
                detector_available=self._detector_available,
            )
            return True

        self._queue_state = "blocked_unknown_command"
        gesture_debug_log(
            "controller.dispatch_blocked",
            raw_gesture=self._raw_gesture,
            stable_gesture=self._stable_gesture,
            confidence=self._confidence,
            resolved_command=command_name,
            queue_state=self._queue_state,
            detector_available=self._detector_available,
        )
        return False

    def mark_command_dispatched(self, command_name: str) -> None:
        self._last_command = command_name
        self._last_dispatched_command = command_name
        self._last_dispatched_at = monotonic()
        if command_name in self.ONE_SHOT_COMMANDS:
            self._armed_oneshot_command = command_name
        self._queue_state = "sent"
        self._pending_command = None
        gesture_debug_log(
            "controller.dispatched",
            raw_gesture=self._raw_gesture,
            stable_gesture=self._stable_gesture,
            confidence=self._confidence,
            resolved_command=command_name,
            queue_state=self._queue_state,
            detector_available=self._detector_available,
        )

    def finalize_dispatch(self, command_name: str) -> dict[str, str | float | bool | None]:
        self.mark_command_dispatched(command_name)
        return self.get_debug_state()

    def get_stable_ms(self) -> int | None:
        if not self._last_stable_gesture_name or self._stable_since <= 0.0:
            return None
        return max(0, int((monotonic() - self._stable_since) * 1000.0))

    def get_threshold_for_gesture(self, stable_gesture: str | None) -> float:
        return GestureInferenceService.get_threshold_for_gesture(stable_gesture)

    def normalize_block_reason(self, command_name: str | None) -> str:
        if not self._enabled:
            return "gesture_off"
        if not self._detector_available:
            return "detector_unavailable"
        if not command_name:
            text = (self._queue_state or "").strip().lower()
            return text if text else "no_command"
        return (self._queue_state or "no_command").strip().lower()

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
            "stable_ms": self.get_stable_ms(),
            "threshold": self.get_threshold_for_gesture(self._last_stable_gesture_name),
        }
