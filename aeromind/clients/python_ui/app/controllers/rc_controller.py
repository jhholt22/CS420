from __future__ import annotations

from time import monotonic

from app.models.rc_state import RcState
from app.services.api_client import ApiClient
from app.services.api_client import ApiClientError


class RcController:
    """Tracks stick state and throttles rc command sends."""

    def __init__(
        self,
        api_client: ApiClient,
        deadzone: int = 8,
        send_interval_ms: int = 180,
    ) -> None:
        self.api_client = api_client
        self.deadzone = max(0, int(deadzone))
        self.send_interval_ms = max(1, int(send_interval_ms))
        self.current_state = RcState()
        self.last_sent_state: RcState | None = None
        self._last_sent_at = 0.0

    def set_left_stick(self, x: int, y: int) -> None:
        self.current_state.yaw = self._clamp(x)
        self.current_state.ud = self._clamp(y)

    def set_right_stick(self, x: int, y: int) -> None:
        self.current_state.lr = self._clamp(x)
        self.current_state.fb = self._clamp(y)

    def flush(self, force: bool = False) -> None:
        state_to_send = self.get_state()
        now = monotonic()

        if self.last_sent_state is not None and state_to_send.is_same_as(self.last_sent_state):
            return

        if not force and ((now - self._last_sent_at) * 1000.0) < self.send_interval_ms:
            return

        raw_rc_command = self._build_raw_rc_command(state_to_send)
        self.api_client.send_command(raw_rc_command)
        self.last_sent_state = state_to_send.copy()
        self._last_sent_at = now

    def reset(self) -> None:
        neutral_state = RcState()
        self.current_state = neutral_state

        if self.last_sent_state is not None and self.last_sent_state.is_same_as(neutral_state):
            return

        try:
            raw_rc_command = self._build_raw_rc_command(neutral_state)
            self.api_client.send_command(raw_rc_command)
            self.last_sent_state = neutral_state.copy()
            self._last_sent_at = monotonic()
        except ApiClientError:
            self.last_sent_state = neutral_state.copy()

    def get_state(self) -> RcState:
        return self.current_state.copy().clamp().apply_deadzone(self.deadzone)

    def _build_raw_rc_command(self, state: RcState) -> str:
        payload = state.to_payload()
        return f"rc {payload['lr']} {payload['fb']} {payload['ud']} {payload['yaw']}"

    @staticmethod
    def _clamp(value: int) -> int:
        return max(-100, min(100, int(value)))
