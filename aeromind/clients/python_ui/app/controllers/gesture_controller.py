from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

from app.models.gesture_behavior import GestureBehavior, get_gesture_behavior
from app.services.gesture_inference_service import GestureInferenceResult, GestureInferenceService
from app.utils.logging_utils import gesture_debug_log


@dataclass(slots=True)
class GestureDispatchDecision:
    command_name: str | None
    dispatch_allowed: bool
    block_reason: str
    debug_state: dict[str, str | float | bool | None]


class GestureController:
    """Maps stabilized gestures to command behaviors through one decision path."""

    def __init__(self) -> None:
        self._enabled = False
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
        self._detector_status = "detector_unavailable"
        self._detector_error: str | None = None
        self._detector_model_path: str | None = None
        self._required_hits = 0
        self._required_confidence = 0.0

        self._stable_since = 0.0
        self._last_stable_gesture_name: str | None = None

        self._last_active_gesture: str | None = None
        self._last_dispatched_gesture: str | None = None
        self._last_command_sent: str | None = None
        self._last_command_timestamp = 0.0
        self._active_repeatable_command: str | None = None
        self._armed_oneshot_command: str | None = None
        self._armed_oneshot_gesture: str | None = None

    def update_from_result(self, result: GestureInferenceResult) -> dict[str, str | float | bool | None]:
        if not self._enabled:
            self.reset()
            return self.get_debug_state()

        self._raw_gesture = result.raw_gesture or "-"
        self._stable_gesture = result.stable_gesture or "-"
        self._confidence = result.confidence
        self._pending_command = result.command_name
        self._queue_state = result.queue_state or "idle"
        self._detector_available = result.detector_available
        self._detector_status = result.detector_status
        self._detector_error = result.detector_error
        self._detector_model_path = result.detector_model_path
        self._required_hits = result.required_hits
        self._required_confidence = result.required_confidence

        now = monotonic()
        current_stable = result.stable_gesture
        if current_stable != self._last_stable_gesture_name:
            self._stable_since = now if current_stable else 0.0
        self._last_stable_gesture_name = current_stable

        current_marker = self._active_marker(result)
        if self._active_repeatable_command is not None and current_marker != self._last_dispatched_gesture:
            self._active_repeatable_command = None
        self._last_active_gesture = current_marker

        self._maybe_release_oneshot(result)
        return self.get_debug_state()

    def evaluate_result(self, result: GestureInferenceResult) -> GestureDispatchDecision:
        debug_state = dict(self.update_from_result(result))
        behavior = get_gesture_behavior(result.stable_gesture)
        command_name = behavior.command if behavior is not None else result.command_name
        behavior_type = behavior.behavior_type if behavior is not None else None
        now = monotonic()

        action = "blocked"
        reason = self.normalize_block_reason(command_name)
        dispatch_allowed = False

        if not self._enabled:
            self._queue_state = "gesture_off"
            reason = "gesture_off"
        elif not self._detector_available:
            self._queue_state = self._detector_status
            reason = self._detector_status
        elif behavior is None or command_name is None:
            reason = self.normalize_block_reason(command_name)
        elif result.queue_state not in {"ready", "debug_bypass"}:
            self._queue_state = result.queue_state
            reason = self.normalize_block_reason(command_name)
        else:
            dispatch_allowed, action, reason = self._decide_behavior_action(
                behavior=behavior,
                now=now,
            )

        debug_state.update(
            {
                "resolved_command": command_name,
                "behavior_type": behavior_type,
                "dispatch_allowed": dispatch_allowed,
                "block_reason": reason,
                "inference_queue_state": result.queue_state,
                "controller_queue_state": self._queue_state,
                "last_active_gesture": self._last_active_gesture,
                "last_command_sent": self._last_command_sent,
                "active_repeatable_command": self._active_repeatable_command,
            }
        )
        gesture_debug_log(
            "controller.behavior_decision",
            gesture=result.stable_gesture or result.raw_gesture,
            command=command_name,
            behavior_type=behavior_type,
            action=action,
            reason=reason,
            queue_state=self._queue_state,
            confidence=result.confidence,
        )
        return GestureDispatchDecision(
            command_name=command_name,
            dispatch_allowed=dispatch_allowed,
            block_reason=reason,
            debug_state=debug_state,
        )

    def finalize_dispatch(self, command_name: str) -> dict[str, str | float | bool | None]:
        self.mark_command_dispatched(command_name)
        return self.get_debug_state()

    def mark_command_dispatched(self, command_name: str) -> None:
        behavior = get_gesture_behavior(self._last_stable_gesture_name or self._raw_gesture)
        self._last_command = command_name
        self._last_command_sent = command_name
        self._last_command_timestamp = monotonic()
        self._last_dispatched_gesture = self._last_stable_gesture_name or self._raw_gesture or None

        if behavior is not None:
            if behavior.behavior_type == "one_shot":
                self._armed_oneshot_command = command_name
                self._armed_oneshot_gesture = behavior.gesture
                self._active_repeatable_command = None
                gesture_debug_log(
                    "controller.oneshot_armed",
                    gesture=behavior.gesture,
                    command=command_name,
                    behavior_type=behavior.behavior_type,
                    action="sent",
                    reason="one_shot_armed",
                )
            elif behavior.behavior_type == "repeatable":
                self._active_repeatable_command = command_name
                gesture_debug_log(
                    "controller.repeatable_active",
                    gesture=behavior.gesture,
                    command=command_name,
                    behavior_type=behavior.behavior_type,
                    action="sent",
                    reason="repeatable_active",
                )
            elif behavior.behavior_type == "safety":
                self._armed_oneshot_command = None
                self._armed_oneshot_gesture = None
                self._active_repeatable_command = None
                gesture_debug_log(
                    "controller.safety_reset",
                    gesture=behavior.gesture,
                    command=command_name,
                    behavior_type=behavior.behavior_type,
                    action="sent",
                    reason="safety_immediate",
                )

        self._queue_state = "sent"
        self._pending_command = None

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
            return (self._detector_status or "detector_unavailable").strip().lower()
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
            "detector_status": self._detector_status,
            "detector_error": self._detector_error,
            "detector_model_path": self._detector_model_path,
            "stable_ms": self.get_stable_ms(),
            "threshold": self.get_threshold_for_gesture(self._last_stable_gesture_name),
            "required_hits": self._required_hits,
            "required_confidence": self._required_confidence,
            "last_active_gesture": self._last_active_gesture,
            "last_dispatched_gesture": self._last_dispatched_gesture,
            "last_command_sent": self._last_command_sent,
            "last_command_timestamp": int(self._last_command_timestamp * 1000.0) if self._last_command_timestamp else None,
            "active_repeatable_command": self._active_repeatable_command,
        }

    def _decide_behavior_action(
        self,
        *,
        behavior: GestureBehavior,
        now: float,
    ) -> tuple[bool, str, str]:
        elapsed_ms = (now - self._last_command_timestamp) * 1000.0

        if behavior.behavior_type == "safety":
            if self._last_dispatched_gesture == behavior.gesture and self._last_command_sent == behavior.command:
                self._queue_state = "waiting_release"
                return False, "waiting_release", "safety_held"
            self._queue_state = "dispatch"
            self._armed_oneshot_command = None
            self._armed_oneshot_gesture = None
            self._active_repeatable_command = None
            return True, "sent", "safety_priority"

        if behavior.behavior_type == "one_shot":
            if behavior.requires_release and self._armed_oneshot_command == behavior.command:
                self._queue_state = "waiting_release"
                return False, "waiting_release", "release_required"
            if self._last_command_sent == behavior.command and elapsed_ms < behavior.cooldown_ms:
                self._queue_state = "cooldown"
                gesture_debug_log(
                    "controller.oneshot_cooldown_active",
                    gesture=behavior.gesture,
                    command=behavior.command,
                    behavior_type=behavior.behavior_type,
                    action="cooldown",
                    reason="cooldown_active",
                    cooldown_remaining_ms=max(0, int(behavior.cooldown_ms - elapsed_ms)),
                )
                return False, "cooldown", "cooldown_active"
            if self._armed_oneshot_gesture != behavior.gesture and self._last_command_sent == behavior.command:
                gesture_debug_log(
                    "controller.oneshot_rearmed",
                    gesture=behavior.gesture,
                    command=behavior.command,
                    behavior_type=behavior.behavior_type,
                    action="rearmed",
                    reason="gesture_changed",
                )
            self._queue_state = "dispatch"
            return True, "sent", "one_shot_ready"

        if self._last_command_sent == behavior.command and elapsed_ms < behavior.cooldown_ms:
            self._queue_state = "cooldown"
            return False, "cooldown", "cooldown_active"

        self._queue_state = "dispatch"
        return True, "sent", "repeatable_ready"

    def _maybe_release_oneshot(self, result: GestureInferenceResult) -> None:
        if self._armed_oneshot_command is None or self._armed_oneshot_gesture is None:
            return

        current_marker = self._active_marker(result)
        if current_marker == self._armed_oneshot_gesture:
            return

        released_command = self._armed_oneshot_command
        released_gesture = self._armed_oneshot_gesture
        self._armed_oneshot_command = None
        self._armed_oneshot_gesture = None
        if self._active_repeatable_command is not None and current_marker != self._last_active_gesture:
            self._active_repeatable_command = None
        gesture_debug_log(
            "controller.oneshot_released",
            gesture=released_gesture,
            command=released_command,
            behavior_type="one_shot",
            action="released",
            reason="gesture_changed",
            release_marker=current_marker or "-",
        )

    @staticmethod
    def _active_marker(result: GestureInferenceResult) -> str | None:
        stable = (result.stable_gesture or "").strip().lower()
        raw = (result.raw_gesture or "").strip().lower()
        if stable:
            return stable
        if raw:
            return raw
        return None
