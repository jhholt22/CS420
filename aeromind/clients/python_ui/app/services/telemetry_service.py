from __future__ import annotations

from app.models.telemetry_state import TelemetryState


class TelemetryService:
    """Maps raw API payloads into typed telemetry state."""

    def build_telemetry(self, status_data: dict, state_data: object, diag_data: object = None) -> TelemetryState:
        safe_status = status_data if isinstance(status_data, dict) else {}
        safe_state = state_data if isinstance(state_data, dict) else None
        safe_diag = diag_data if isinstance(diag_data, dict) else None
        return TelemetryState.from_api(safe_status, safe_state, safe_diag)
