from __future__ import annotations

from time import monotonic

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.config import AppConfig

class GestureDirectionResolver:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self.reset()

    def reset(self) -> None:
        self._smoothed_tilt: float | None = None
        self._committed_direction = "point_up"
        self._pending_direction: str | None = None
        self._pending_direction_hits = 0
        self._direction_last_changed_at = 0.0

    def resolve(self, *, tilt_value: float | None) -> tuple[str, dict[str, str | float | None]]:
        if tilt_value is None:
            return "point_up", {
                "tilt_value": None,
                "smoothed_tilt": None,
                "candidate_direction": "point_up",
                "resolved_direction": "point_up",
                "direction_reason": "no_tilt",
            }

        smoothed_tilt = self._smooth_tilt(tilt_value)
        candidate_direction, candidate_reason = self._classify_direction_candidate(smoothed_tilt)
        resolved_direction, direction_reason = self._resolve_direction_state(
            candidate_direction=candidate_direction,
            candidate_reason=candidate_reason,
            now=monotonic(),
        )
        return resolved_direction, {
            "tilt_value": tilt_value,
            "smoothed_tilt": smoothed_tilt,
            "candidate_direction": candidate_direction,
            "resolved_direction": resolved_direction,
            "direction_reason": direction_reason,
        }

    def _smooth_tilt(self, tilt_value: float | None) -> float | None:
        if tilt_value is None:
            return self._smoothed_tilt
        alpha = max(0.0, min(1.0, self._config.gesture_tilt_smoothing_alpha))
        if self._smoothed_tilt is None:
            self._smoothed_tilt = tilt_value
        else:
            self._smoothed_tilt = (alpha * tilt_value) + ((1.0 - alpha) * self._smoothed_tilt)
        return self._smoothed_tilt

    def _classify_direction_candidate(self, tilt_value: float | None) -> tuple[str, str]:
        if tilt_value is None:
            return self._committed_direction, "no_tilt"
        if self._committed_direction == "point_left" and tilt_value <= -self._config.gesture_tilt_exit_threshold:
            return "point_left", "hysteresis_hold"
        if self._committed_direction == "point_right" and tilt_value >= self._config.gesture_tilt_exit_threshold:
            return "point_right", "hysteresis_hold"
        if abs(tilt_value) <= self._config.gesture_tilt_neutral_dead_zone:
            return "point_up", "dead_zone"
        if tilt_value <= -self._config.gesture_tilt_enter_threshold:
            return "point_left", "enter_left"
        if tilt_value >= self._config.gesture_tilt_enter_threshold:
            return "point_right", "enter_right"
        if self._committed_direction in {"point_left", "point_right"}:
            return self._committed_direction, "hysteresis_hold"
        return "point_up", "forward_bias"

    def _resolve_direction_state(
        self,
        *,
        candidate_direction: str,
        candidate_reason: str,
        now: float,
    ) -> tuple[str, str]:
        if candidate_direction == self._committed_direction:
            self._pending_direction = None
            self._pending_direction_hits = 0
            return self._committed_direction, candidate_reason

        if (
            self._direction_last_changed_at > 0.0
            and ((now - self._direction_last_changed_at) * 1000.0) < self._config.gesture_direction_min_hold_ms
        ):
            return self._committed_direction, "hold"

        if self._pending_direction != candidate_direction:
            self._pending_direction = candidate_direction
            self._pending_direction_hits = 1
            return self._committed_direction, "stabilizing"

        self._pending_direction_hits += 1
        if self._pending_direction_hits < max(1, self._config.gesture_direction_stabilization_hits):
            return self._committed_direction, "stabilizing"

        self._committed_direction = candidate_direction
        self._direction_last_changed_at = now
        self._pending_direction = None
        self._pending_direction_hits = 0
        return self._committed_direction, "changed"
