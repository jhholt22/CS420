from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

from app.config import AppConfig
from app.models.gesture_behavior import GestureBehavior, get_gesture_behavior
from app.services.gesture_inference_service import GestureInferenceResult
from app.utils.logging_utils import gesture_debug_log


@dataclass(slots=True)
class GestureDispatchDecision:
    command_name: str | None
    dispatch_allowed: bool
    block_reason: str
    debug_state: dict[str, str | float | bool | None]


class GestureController:
    """Maps stabilized gestures to command behaviors through one decision path."""

    _TERMINAL_COMMANDS = frozenset({"takeoff", "land", "emergency"})
    _CONTINUOUS_COMMANDS = frozenset(
        {"forward", "back", "left", "right", "rotate_left", "rotate_right", "up", "down"}
    )
    _NEUTRAL_COMMANDS = frozenset({"stop", "hover"})

    def __init__(self, config: AppConfig | None = None) -> None:
        self._config = config or AppConfig()
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
        self._stability_gesture_name: str | None = None
        self._pending_stability_gesture_name: str | None = None
        self._pending_stability_since = 0.0
        self._last_stable_gesture_name: str | None = None

        self._last_active_gesture: str | None = None
        self._last_dispatched_gesture: str | None = None
        self._last_command_sent: str | None = None
        self._last_command_timestamp = 0.0
        self._active_repeatable_command: str | None = None
        self._active_movement_command: str | None = None
        self._active_movement_gesture: str | None = None
        self._last_movement_send_at = 0.0
        self._pending_movement_stop_reason: str | None = None
        self._armed_oneshot_command: str | None = None
        self._armed_oneshot_gesture: str | None = None
        self._release_started_at = 0.0
        self._latched_terminal_command: str | None = None
        self._latched_terminal_gesture: str | None = None
        self._latched_terminal_since = 0.0

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
        observed_stable = result.stable_gesture
        self._last_stable_gesture_name = observed_stable
        self._update_stability_tracking(observed_stable, now=now)
        self._stable_gesture = self._stability_gesture_name or "-"

        current_marker = self._active_marker(result)
        if self._active_repeatable_command is not None and current_marker != self._last_dispatched_gesture:
            self._active_repeatable_command = None
        self._last_active_gesture = current_marker

        self._maybe_release_oneshot(result, now=now)
        return self.get_debug_state()

    def evaluate_result(self, result: GestureInferenceResult) -> GestureDispatchDecision:
        debug_state = dict(self.update_from_result(result))
        behavior = get_gesture_behavior(result.stable_gesture)

        if behavior is None and result.command_name and (result.raw_gesture or "").strip().lower() == "open_palm":
            behavior = get_gesture_behavior(result.raw_gesture)

        if behavior is None and self._stability_gesture_name:
            committed_behavior = get_gesture_behavior(self._stability_gesture_name)
            if committed_behavior is not None and committed_behavior.behavior_type == "repeatable":
                behavior = committed_behavior

        command_name = behavior.command if behavior is not None else result.command_name
        behavior_type = behavior.behavior_type if behavior is not None else None
        now = monotonic()
        stable_ms = self.get_stable_ms()
        self._expire_terminal_latch_if_needed(now)

        action = "blocked"
        reason = self.normalize_block_reason(command_name)
        dispatch_allowed = False

        if self._terminal_lock_active(now):
            elapsed_ms = int((now - self._latched_terminal_since) * 1000.0)
            gesture_debug_log(
                "controller.terminal_lock_active",
                incoming_gesture=result.stable_gesture or result.raw_gesture or "-",
                incoming_command=command_name or "-",
                latched_terminal_command=self._latched_terminal_command or "-",
                elapsed_ms=elapsed_ms,
            )
            if command_name == "emergency":
                gesture_debug_log(
                    "controller.terminal_emergency_override",
                    incoming_gesture=result.stable_gesture or result.raw_gesture or "-",
                    incoming_command=command_name,
                    latched_terminal_command=self._latched_terminal_command or "-",
                    elapsed_ms=elapsed_ms,
                )
                self._clear_terminal_latch(reason="emergency_override")
            elif self._latched_terminal_command is not None:
                self._queue_state = "terminal_latched"
                gesture_debug_log(
                    "controller.terminal_lock_blocked",
                    incoming_gesture=result.stable_gesture or result.raw_gesture or "-",
                    incoming_command=command_name or "-",
                    latched_terminal_command=self._latched_terminal_command,
                    elapsed_ms=elapsed_ms,
                )
                debug_state.update(
                    {
                        "resolved_command": command_name,
                        "behavior_type": behavior_type,
                        "dispatch_allowed": False,
                        "block_reason": "terminal_locked",
                        "inference_queue_state": result.queue_state,
                        "controller_queue_state": self._queue_state,
                        "last_active_gesture": self._last_active_gesture,
                        "last_command_sent": self._last_command_sent,
                        "active_repeatable_command": self._active_repeatable_command,
                        "active_movement_command": self._active_movement_command,
                        "active_movement_gesture": self._active_movement_gesture,
                        "pending_movement_stop_reason": self._pending_movement_stop_reason,
                        "latched_terminal_command": self._latched_terminal_command,
                        "latched_terminal_gesture": self._latched_terminal_gesture,
                        "terminal_lock_active": True,
                    }
                )
                return GestureDispatchDecision(
                    command_name=command_name,
                    dispatch_allowed=False,
                    block_reason="terminal_locked",
                    debug_state=debug_state,
                )

        if not self._enabled:
            self._queue_state = "gesture_off"
            reason = "gesture_off"
            dispatch_allowed, action, reason, command_name = self._resolve_movement_stop(
                now=now,
                reason="gesture_off",
            )
        elif not self._detector_available:
            self._queue_state = self._detector_status
            reason = self._detector_status
            dispatch_allowed, action, reason, command_name = self._resolve_movement_stop(
                now=now,
                reason=self._detector_status,
            )
        elif behavior is not None and behavior.behavior_type == "safety" and result.queue_state in {"ready", "debug_bypass"}:
            dispatch_allowed, action, reason = self._decide_behavior_action(
                behavior=behavior,
                now=now,
                result=result,
                stable_ms=stable_ms,
            )
        elif behavior is None or command_name is None:
            reason = self.normalize_block_reason(command_name)
            dispatch_allowed, action, reason, command_name = self._resolve_movement_stop(
                now=now,
                reason="movement_lost" if self._active_movement_command else reason,
            )
        elif result.queue_state not in {"ready", "debug_bypass"}:
            self._queue_state = result.queue_state
            reason = self.normalize_block_reason(command_name)
            dispatch_allowed, action, reason, command_name = self._resolve_movement_stop(
                now=now,
                reason="movement_blocked" if behavior.behavior_type == "repeatable" else reason,
            )
        else:
            dispatch_allowed, action, reason = self._decide_behavior_action(
                behavior=behavior,
                now=now,
                result=result,
                stable_ms=stable_ms,
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
                "active_movement_command": self._active_movement_command,
                "active_movement_gesture": self._active_movement_gesture,
                "pending_movement_stop_reason": self._pending_movement_stop_reason,
                "latched_terminal_command": self._latched_terminal_command,
                "latched_terminal_gesture": self._latched_terminal_gesture,
                "terminal_lock_active": self._terminal_lock_active(now),
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
        if command_name in {"hover", "stop"} and self._pending_movement_stop_reason is not None:
            behavior = None

        was_same_movement = (
            behavior is not None
            and behavior.behavior_type == "repeatable"
            and self._active_movement_command == command_name
            and self._active_movement_gesture == behavior.gesture
        )

        self._last_command = command_name
        self._last_command_sent = command_name
        self._last_command_timestamp = monotonic()
        self._last_dispatched_gesture = self._last_stable_gesture_name or self._raw_gesture or None

        if behavior is not None:
            if behavior.behavior_type == "one_shot":
                self._armed_oneshot_command = command_name
                self._armed_oneshot_gesture = behavior.gesture
                self._active_repeatable_command = None
                self._active_movement_command = None
                self._active_movement_gesture = None

                if self._is_terminal_command(command_name) and self._terminal_latch_enabled:
                    if self._latched_terminal_command is not None and self._latched_terminal_command != command_name:
                        self._clear_terminal_latch(reason="terminal_override")
                    self._latched_terminal_command = command_name
                    self._latched_terminal_gesture = behavior.gesture
                    self._latched_terminal_since = monotonic()
                    gesture_debug_log(
                        "controller.terminal_command_latched",
                        gesture=behavior.gesture,
                        command=command_name,
                        action="latched",
                        reason="terminal_latched",
                    )

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
                self._active_movement_command = command_name
                self._active_movement_gesture = behavior.gesture
                self._last_movement_send_at = monotonic()
                self._pending_movement_stop_reason = None

                if not was_same_movement:
                    gesture_debug_log(
                        "controller.movement_state_started",
                        gesture=behavior.gesture,
                        command=command_name,
                        behavior_type=behavior.behavior_type,
                        action="active",
                        reason="movement_active",
                    )

            elif behavior.behavior_type == "safety":
                self._clear_terminal_latch(reason="safety_override")
                self._armed_oneshot_command = None
                self._armed_oneshot_gesture = None
                self._active_repeatable_command = None
                self._active_movement_command = None
                self._active_movement_gesture = None
                self._pending_movement_stop_reason = None

                gesture_debug_log(
                    "controller.safety_reset",
                    gesture=behavior.gesture,
                    command=command_name,
                    behavior_type=behavior.behavior_type,
                    action="sent",
                    reason="safety_immediate",
                )

        elif command_name in {"hover", "stop"}:
            self._clear_terminal_latch(reason="neutral_override")
            self._active_repeatable_command = None
            self._active_movement_command = None
            self._active_movement_gesture = None
            self._last_movement_send_at = monotonic()

            gesture_debug_log(
                "controller.movement_state_stopped",
                gesture=self._last_dispatched_gesture or "-",
                command=command_name,
                action="stop",
                reason=self._pending_movement_stop_reason or "movement_stop",
            )
            self._pending_movement_stop_reason = None

        self._queue_state = "sent"
        self._pending_command = None

    def get_stable_ms(self) -> int | None:
        if not self._stability_gesture_name or self._stable_since <= 0.0:
            return None
        return max(0, int((monotonic() - self._stable_since) * 1000.0))

    def get_threshold_for_gesture(self, stable_gesture: str | None) -> float:
        return self._config.gesture_min_confidence(stable_gesture)

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
            "threshold": self._required_confidence or self.get_threshold_for_gesture(self._last_stable_gesture_name),
            "required_hits": self._required_hits,
            "required_confidence": self._required_confidence,
            "last_active_gesture": self._last_active_gesture,
            "stability_gesture": self._stability_gesture_name,
            "stability_pending_gesture": self._pending_stability_gesture_name,
            "last_dispatched_gesture": self._last_dispatched_gesture,
            "last_command_sent": self._last_command_sent,
            "last_command_timestamp": int(self._last_command_timestamp * 1000.0) if self._last_command_timestamp else None,
            "active_repeatable_command": self._active_repeatable_command,
            "active_movement_command": self._active_movement_command,
            "active_movement_gesture": self._active_movement_gesture,
            "pending_movement_stop_reason": self._pending_movement_stop_reason,
            "one_shot_stabilization_ms": self._config.gesture_stability.one_shot_stabilization_ms,
            "movement_stabilization_ms": self._config.gesture_stability.movement_stabilization_ms,
            "movement_resend_interval_ms": self._config.gesture_motion.movement_resend_interval_ms,
            "movement_cooldown_ms": self._config.gesture_motion.movement_cooldown_ms,
            "movement_fast_path_confidence": self._config.gesture_motion.movement_fast_path_confidence,
            "release_window_ms": self._config.gesture_stability.release_window_ms,
            "terminal_command_latch_enabled": self._terminal_latch_enabled,
            "terminal_command_cooldown_ms": self._terminal_command_cooldown_ms,
            "terminal_command_release_required": self._terminal_release_required,
            "latched_terminal_command": self._latched_terminal_command,
            "latched_terminal_gesture": self._latched_terminal_gesture,
        }

    @property
    def _release_window_ms(self) -> int:
        return max(0, int(self._config.gesture_stability.release_window_ms))

    @property
    def _stability_reset_debounce_ms(self) -> int:
        return max(0, int(self._config.gesture_stability.stability_reset_debounce_ms))

    @property
    def _movement_resend_interval_ms(self) -> int:
        return max(1, int(self._config.gesture_motion.movement_resend_interval_ms))

    @property
    def _movement_cooldown_ms(self) -> int:
        return max(0, int(self._config.gesture_motion.movement_cooldown_ms))

    @property
    def _movement_stabilization_ms(self) -> int:
        return max(0, int(self._config.gesture_stability.movement_stabilization_ms))

    def _required_stabilization_ms(self, gesture_name: str | None) -> int:
        return max(0, int(self._config.gesture_stabilization_ms(gesture_name)))

    def _fast_path_confidence_for_gesture(self, gesture_name: str | None) -> float:
        return max(0.0, min(1.0, float(self._config.gesture_fast_path_confidence(gesture_name))))

    def _decide_behavior_action(
        self,
        *,
        behavior: GestureBehavior,
        now: float,
        result: GestureInferenceResult,
        stable_ms: int | None,
    ) -> tuple[bool, str, str]:
        elapsed_ms = (now - self._last_command_timestamp) * 1000.0

        if self._terminal_lock_active(now) and self._latched_terminal_command is not None:
            elapsed_lock_ms = int((now - self._latched_terminal_since) * 1000.0)
            if behavior.command == "emergency":
                gesture_debug_log(
                    "controller.terminal_emergency_override",
                    incoming_gesture=behavior.gesture,
                    incoming_command=behavior.command,
                    latched_terminal_command=self._latched_terminal_command,
                    elapsed_ms=elapsed_lock_ms,
                )
                self._clear_terminal_latch(reason="emergency_override")
            elif behavior.command != self._latched_terminal_command:
                self._queue_state = "terminal_latched"
                gesture_debug_log(
                    "controller.terminal_lock_blocked",
                    incoming_gesture=behavior.gesture,
                    incoming_command=behavior.command,
                    latched_terminal_command=self._latched_terminal_command,
                    elapsed_ms=elapsed_lock_ms,
                )
                return False, "terminal_latched", "terminal_locked"

        if behavior.behavior_type == "safety":
            if self._last_dispatched_gesture == behavior.gesture and self._last_command_sent == behavior.command:
                self._queue_state = "waiting_release"
                return False, "waiting_release", "waiting_release"

            self._queue_state = "dispatch"
            self._armed_oneshot_command = None
            self._armed_oneshot_gesture = None
            self._active_repeatable_command = None
            self._active_movement_command = None
            self._active_movement_gesture = None
            return True, "sent", "safety_priority"

        if behavior.behavior_type == "one_shot":
            if self._is_terminal_command(behavior.command):
                terminal_dispatch = self._evaluate_terminal_command(
                    behavior=behavior,
                    now=now,
                    stable_ms=stable_ms,
                )
                if terminal_dispatch is not None:
                    return terminal_dispatch

            if not self._meets_one_shot_stability(stable_ms):
                self._queue_state = "stabilizing"
                return False, "stabilizing", "stabilizing"

            if behavior.requires_release and self._armed_oneshot_command == behavior.command:
                self._queue_state = "waiting_release"
                return False, "waiting_release", "waiting_release"

            if self._last_command_sent == behavior.command and elapsed_ms < behavior.cooldown_ms:
                self._queue_state = "cooldown"
                gesture_debug_log(
                    "controller.oneshot_cooldown_active",
                    gesture=behavior.gesture,
                    command=behavior.command,
                    behavior_type=behavior.behavior_type,
                    action="cooldown",
                    reason="cooldown",
                    cooldown_remaining_ms=max(0, int(behavior.cooldown_ms - elapsed_ms)),
                )
                return False, "cooldown", "cooldown"

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

        if not self._movement_ready_to_activate(result=result, stable_ms=stable_ms):
            self._queue_state = "stabilizing"
            return False, "stabilizing", "stabilizing"

        resend_elapsed_ms = (now - self._last_movement_send_at) * 1000.0 if self._last_movement_send_at > 0.0 else None

        if self._active_movement_command == behavior.command and self._active_movement_gesture == behavior.gesture:
            if resend_elapsed_ms is not None and resend_elapsed_ms < self._movement_resend_interval_ms:
                self._queue_state = "movement_active"
                return False, "movement_active", "movement_active"

            self._queue_state = "dispatch"
            gesture_debug_log(
                "controller.movement_resend_ready",
                gesture=behavior.gesture,
                command=behavior.command,
                resend_elapsed_ms=int(resend_elapsed_ms or 0),
                resend_interval_ms=self._movement_resend_interval_ms,
            )
            return True, "sent", "movement_resend"

        if elapsed_ms < self._movement_cooldown_ms:
            self._queue_state = "cooldown"
            return False, "cooldown", "cooldown"

        self._queue_state = "dispatch"
        return True, "sent", "movement_ready"

    def _maybe_release_oneshot(self, result: GestureInferenceResult, *, now: float) -> None:
        if self._armed_oneshot_command is None or self._armed_oneshot_gesture is None:
            self._release_started_at = 0.0
            return

        current_marker = self._active_marker(result)
        if current_marker == self._armed_oneshot_gesture:
            self._release_started_at = 0.0
            return

        release_reason = "gesture_changed"
        if current_marker is None:
            if self._release_started_at <= 0.0:
                self._release_started_at = now
                return

            elapsed_ms = (now - self._release_started_at) * 1000.0
            if elapsed_ms < self._release_window_ms:
                return

            release_reason = "no_hand_timeout"
        else:
            self._release_started_at = 0.0

        released_command = self._armed_oneshot_command
        released_gesture = self._armed_oneshot_gesture
        is_terminal = self._is_terminal_command(released_command)

        if is_terminal:
            gesture_debug_log(
                "controller.terminal_release_ignored",
                gesture=released_gesture,
                command=released_command,
                action="ignored",
                reason=release_reason,
                release_marker=current_marker or "-",
            )
            self._release_started_at = 0.0
            return

        self._armed_oneshot_command = None
        self._armed_oneshot_gesture = None
        self._release_started_at = 0.0

        if self._active_repeatable_command is not None and current_marker != self._last_active_gesture:
            self._active_repeatable_command = None

        gesture_debug_log(
            "controller.oneshot_released",
            gesture=released_gesture,
            command=released_command,
            behavior_type="one_shot",
            action="released",
            reason=release_reason,
            release_marker=current_marker or "-",
        )
        gesture_debug_log(
            "controller.waiting_release_cleared",
            gesture=released_gesture,
            command=released_command,
            reason=release_reason,
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

    def _update_stability_tracking(self, observed_stable: str | None, *, now: float) -> None:
        if observed_stable == self._stability_gesture_name:
            self._pending_stability_gesture_name = None
            self._pending_stability_since = 0.0
            if observed_stable is not None and self._stable_since <= 0.0:
                self._stable_since = now
            return

        if observed_stable != self._pending_stability_gesture_name:
            self._pending_stability_gesture_name = observed_stable
            self._pending_stability_since = now
            return

        if self._pending_stability_since <= 0.0:
            self._pending_stability_since = now
            return

        debounce_elapsed_ms = (now - self._pending_stability_since) * 1000.0
        if debounce_elapsed_ms < self._stability_reset_debounce_ms:
            return

        self._stability_gesture_name = observed_stable
        self._stable_since = self._pending_stability_since if observed_stable is not None else 0.0
        self._pending_stability_gesture_name = None
        self._pending_stability_since = 0.0

    def _movement_ready_to_activate(self, *, result: GestureInferenceResult, stable_ms: int | None) -> bool:
        if stable_ms is not None and stable_ms >= self._required_stabilization_ms(result.stable_gesture):
            return True
        if result.confidence is None:
            return False
        if result.confidence < self._fast_path_confidence_for_gesture(result.stable_gesture):
            return False
        return result.stable_hits >= max(1, min(self._required_hits or 1, 2))

    def _meets_one_shot_stability(self, stable_ms: int | None) -> bool:
        if stable_ms is None:
            return False
        return stable_ms >= self._required_stabilization_ms(self._last_stable_gesture_name)

    def _resolve_movement_stop(
        self,
        *,
        now: float,
        reason: str,
    ) -> tuple[bool, str, str, str | None]:
        if self._active_movement_command is None:
            return False, "blocked", reason, None

        if self._pending_movement_stop_reason is None:
            self._pending_movement_stop_reason = reason
            gesture_debug_log(
                "controller.movement_stop_requested",
                gesture=self._active_movement_gesture or "-",
                command=self._active_movement_command,
                reason=reason,
            )

        resend_elapsed_ms = (now - self._last_movement_send_at) * 1000.0 if self._last_movement_send_at > 0.0 else None
        if resend_elapsed_ms is not None and resend_elapsed_ms < self._movement_cooldown_ms:
            self._queue_state = "movement_stop_pending"
            return False, "movement_stop_pending", "movement_stop_pending", "hover"

        self._queue_state = "dispatch"
        return True, "sent", self._pending_movement_stop_reason or reason, "hover"

    @property
    def _terminal_latch_enabled(self) -> bool:
        return bool(self._config.gesture_terminal.terminal_command_latch_enabled)

    @property
    def _terminal_command_cooldown_ms(self) -> int:
        return max(0, int(self._config.gesture_terminal.terminal_command_cooldown_ms))

    @property
    def _terminal_release_required(self) -> bool:
        return bool(self._config.gesture_terminal.terminal_command_release_required)

    @classmethod
    def _is_terminal_command(cls, command_name: str | None) -> bool:
        return command_name in cls._TERMINAL_COMMANDS

    def _evaluate_terminal_command(
        self,
        *,
        behavior: GestureBehavior,
        now: float,
        stable_ms: int | None,
    ) -> tuple[bool, str, str] | None:
        if not self._terminal_latch_enabled:
            return None

        if not self._meets_one_shot_stability(stable_ms):
            self._queue_state = "stabilizing"
            return False, "stabilizing", "stabilizing"

        if self._latched_terminal_command == behavior.command:
            self._queue_state = "terminal_latched"
            gesture_debug_log(
                "controller.terminal_command_ignored",
                gesture=behavior.gesture,
                command=behavior.command,
                action="ignored",
                reason="already_latched",
            )
            return False, "terminal_latched", "terminal_locked"

        if self._last_command_sent == behavior.command:
            elapsed_ms = (now - self._last_command_timestamp) * 1000.0
            cooldown_ms = max(int(behavior.cooldown_ms), self._terminal_command_cooldown_ms)
            if elapsed_ms < cooldown_ms:
                self._queue_state = "cooldown"
                return False, "cooldown", "cooldown"

        self._queue_state = "dispatch"
        return True, "sent", "terminal_ready"

    def _clear_terminal_latch(self, *, reason: str) -> None:
        if self._latched_terminal_command is None:
            return

        gesture_debug_log(
            "controller.terminal_command_released",
            gesture=self._latched_terminal_gesture or "-",
            command=self._latched_terminal_command,
            action="released",
            reason=reason,
        )
        self._latched_terminal_command = None
        self._latched_terminal_gesture = None
        self._latched_terminal_since = 0.0

    def _terminal_lock_active(self, now: float) -> bool:
        if self._latched_terminal_command is None or self._latched_terminal_since <= 0.0:
            return False
        elapsed_ms = (now - self._latched_terminal_since) * 1000.0
        return elapsed_ms < self._terminal_command_cooldown_ms

    def _expire_terminal_latch_if_needed(self, now: float) -> None:
        if self._latched_terminal_command is None:
            return
        if self._terminal_lock_active(now):
            return
        elapsed_ms = int((now - self._latched_terminal_since) * 1000.0)
        gesture_debug_log(
            "controller.terminal_lock_expired",
            latched_terminal_command=self._latched_terminal_command,
            incoming_gesture=self._last_stable_gesture_name or self._raw_gesture or "-",
            incoming_command=self._pending_command or "-",
            elapsed_ms=elapsed_ms,
        )
        self._clear_terminal_latch(reason="terminal_timeout")
