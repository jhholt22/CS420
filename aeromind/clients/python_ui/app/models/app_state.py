from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.models.startup_check import StartupSummary
from app.models.telemetry_state import TelemetryState
from app.utils.logging_utils import gesture_debug_log


@dataclass(slots=True)
class UiHealthState:
    detector_ready: bool = False
    detector_error_reason: str | None = None
    drone_connected: bool = False
    sdk_mode_ready: bool = False
    video_connected: bool = False
    last_command_status: str = "idle"
    last_command_error: str | None = None
    current_mode: str = "--"


@dataclass(slots=True)
class AppState:
    connected: bool = False
    mode: str = "--"
    battery_pct: int | None = None
    height_cm: int | None = None
    stream_live: bool = False
    stream_status: str = "No Signal"
    gesture_enabled: bool = False
    last_error: str | None = None
    health: UiHealthState = field(default_factory=UiHealthState)
    startup_summary: StartupSummary | None = None

    def update_from_telemetry(self, telemetry: TelemetryState) -> None:
        self.mode = telemetry.mode
        self.battery_pct = telemetry.battery_pct
        self.height_cm = telemetry.height_cm
        self.last_error = None
        self._update_health(
            source="telemetry",
            reason="status_update",
            drone_connected=telemetry.drone_connected,
            sdk_mode_ready=telemetry.sdk_mode_ready,
            current_mode=telemetry.mode,
        )

    def mark_connected(self, mode: str, *, sdk_mode_ready: bool = False) -> None:
        self.connected = True
        self.mode = mode or "--"
        self.last_error = None
        self._update_health(
            source="runtime",
            reason="connected",
            drone_connected=True,
            sdk_mode_ready=sdk_mode_ready,
            current_mode=self.mode,
        )

    def mark_disconnected(self, error: str | None = None) -> None:
        self.connected = False
        self.mode = "--"
        self.battery_pct = None
        self.height_cm = None
        self.last_error = error
        self._update_health(
            source="runtime",
            reason="disconnected",
            drone_connected=False,
            sdk_mode_ready=False,
            current_mode="--",
        )

    def set_stream_live(self, is_live: bool) -> None:
        self.stream_live = is_live
        self._update_health(source="video", reason="stream_live", video_connected=is_live)

    def set_stream_status(self, status: str) -> None:
        self.stream_status = status.strip() if status else "No Signal"
        self.stream_live = self.stream_status == "Live"
        self._update_health(
            source="video",
            reason=self.stream_status.lower().replace(" ", "_"),
            video_connected=self.stream_live,
        )

    def set_detector_state(self, *, ready: bool, error_reason: str | None) -> None:
        self._update_health(
            source="detector",
            reason="detector_state",
            detector_ready=ready,
            detector_error_reason=error_reason,
        )

    def set_command_status(self, *, status: str, error: str | None = None) -> None:
        self._update_health(
            source="command",
            reason=status,
            last_command_status=status,
            last_command_error=error,
        )

    def reset_runtime_state(self) -> None:
        self.connected = False
        self.mode = "--"
        self.battery_pct = None
        self.height_cm = None
        self.stream_live = False
        self.stream_status = "Stopped"
        self.gesture_enabled = False
        self.last_error = None
        self._update_health(
            source="runtime",
            reason="reset",
            detector_ready=False,
            detector_error_reason=None,
            drone_connected=False,
            sdk_mode_ready=False,
            video_connected=False,
            last_command_status="idle",
            last_command_error=None,
            current_mode="--",
        )

    def set_startup_summary(self, summary: StartupSummary) -> None:
        self.startup_summary = summary
        gesture_debug_log(
            "ui.startup_summary",
            overall_status=summary.overall_status,
            items=[
                {
                    "subsystem": item.subsystem,
                    "status": item.status,
                    "reason": item.reason,
                    "next_action": item.next_action,
                }
                for item in summary.items
            ],
        )

    def _update_health(self, *, source: str, reason: str, **changes: object) -> None:
        previous = asdict(self.health)
        changed = False
        for field_name, value in changes.items():
            if not hasattr(self.health, field_name):
                continue
            if getattr(self.health, field_name) != value:
                setattr(self.health, field_name, value)
                changed = True

        if changed:
            gesture_debug_log(
                "ui.health_changed",
                source=source,
                reason=reason,
                previous=previous,
                new=asdict(self.health),
            )
