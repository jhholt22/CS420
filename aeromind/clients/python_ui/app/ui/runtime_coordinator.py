from __future__ import annotations

from time import time
from typing import Any, Callable

from PySide6.QtCore import QThread

from app.config import AppConfig
from app.controllers.app_controller import AppController
from app.models.app_state import AppState
from app.services.api_client import ApiClientError
from app.services.gesture_inference_service import GestureInferenceService
from app.services.gesture_logger import GestureLogger
from app.services.telemetry_service import TelemetryService
from app.services.video_stream_service import VideoStreamService
from app.utils.logging_utils import gesture_debug_log
from app.workers.status_worker import StatusWorker
from app.workers.video_worker import VideoWorker


class ClientRuntimeCoordinator:
    def __init__(
        self,
        *,
        parent: object,
        config: AppConfig,
        app_controller: AppController,
        app_state: AppState,
        gesture_inference_service: GestureInferenceService,
        gesture_logger: GestureLogger,
        telemetry_service: TelemetryService,
        video_service: VideoStreamService,
    ) -> None:
        self.config = config
        self.app_controller = app_controller
        self.app_state = app_state
        self.gesture_inference_service = gesture_inference_service
        self.gesture_logger = gesture_logger
        self.telemetry_service = telemetry_service
        self.video_service = video_service
        self._last_motion_probe: dict[str, object] | None = None

        self.status_thread = QThread(parent)
        self.status_worker = StatusWorker(self.app_controller.api_client, self.config.status_refresh_ms)
        self.status_worker.moveToThread(self.status_thread)
        self.status_thread.started.connect(self.status_worker.start)

        self.video_thread = QThread(parent)
        self.video_worker = VideoWorker(
            self.video_service,
            self.config.video_url,
            self.config.video_reconnect_delay_ms,
            read_interval_ms=self.config.video_read_interval_ms,
            drop_frames_on_reconnect=self.config.video_drop_frames_on_reconnect,
        )
        self.video_worker.moveToThread(self.video_thread)
        self.video_thread.started.connect(self.video_worker.start)

    def connect_workers(
        self,
        *,
        on_frame_ready: Callable[[object], None],
        on_raw_frame_ready: Callable[[object], None],
        on_stream_status_changed: Callable[[str], None],
        on_status_updated: Callable[[dict, object], None],
        on_status_error: Callable[[str], None],
    ) -> None:
        self.video_worker.frameReady.connect(on_frame_ready)
        self.video_worker.rawFrameReady.connect(on_raw_frame_ready)
        self.video_worker.streamStatusChanged.connect(on_stream_status_changed)
        self.status_worker.statusUpdated.connect(on_status_updated)
        self.status_worker.statusError.connect(on_status_error)

    def start(self) -> None:
        self.status_thread.start()
        self.video_thread.start()

    def stop(self) -> None:
        self._safe_stop_worker(self.status_worker)
        self._safe_quit_thread(self.status_thread, 1500)
        self._safe_stop_worker(self.video_worker)
        self._safe_quit_thread(self.video_thread, 2000)

    def reset_runtime_state(self) -> None:
        self.gesture_inference_service.reset()
        self.app_controller.gesture_controller.disable()
        self.app_state.gesture_enabled = False
        self.app_controller.rc_controller.reset()
        self.video_service.close()
        self.app_state.reset_runtime_state()

    def process_gesture_frame(
        self,
        frame: object,
        *,
        on_api_error: Callable[[str], None],
    ) -> dict[str, str | float | bool | None] | None:
        try:
            result = self.gesture_inference_service.process_frame(frame)
            decision = self.app_controller.gesture_controller.evaluate_result(result)
            debug_state = decision.debug_state
            frame_id = self.gesture_logger.next_frame_id()
            stable_ms = self._as_int(debug_state.get("stable_ms"))
            threshold = self._as_float(debug_state.get("threshold"))
            gesture_debug_log(
                "mainwindow.frame_processed",
                frame_id=frame_id,
                raw_gesture=result.raw_gesture,
                stable_gesture=result.stable_gesture,
                confidence=result.confidence,
                resolved_command=decision.command_name,
                queue_state=debug_state.get("queue_state"),
                detector_available=result.detector_available,
            )
            self.gesture_logger.log_gesture_event(
                frame_id=frame_id,
                gesture_true=self.gesture_logger.get_current_label(),
                gesture_pred=result.raw_gesture,
                stable_gesture=result.stable_gesture,
                confidence=result.confidence,
                stable_ms=stable_ms,
                threshold=threshold,
                drone_state=self.current_drone_state(),
                battery_pct=self.app_state.battery_pct,
                height_cm=self.app_state.height_cm,
            )

            command_name = decision.command_name
            if decision.dispatch_allowed:
                assert command_name is not None
                command_ts = int(time() * 1000)
                gesture_debug_log(
                    "mainwindow.dispatch_attempt",
                    frame_id=frame_id,
                    raw_gesture=result.raw_gesture,
                    stable_gesture=result.stable_gesture,
                    confidence=result.confidence,
                    resolved_command=command_name,
                    queue_state=debug_state.get("queue_state"),
                    detector_available=result.detector_available,
                )
                dispatch_result = self._call_api(
                    lambda: self.app_controller.command_controller.execute_gesture_command(command_name),
                    on_api_error=on_api_error,
                )
                ack_ts = int(time() * 1000) if dispatch_result is not None else None
                gesture_debug_log(
                    "mainwindow.dispatch_result",
                    frame_id=frame_id,
                    raw_gesture=result.raw_gesture,
                    stable_gesture=result.stable_gesture,
                    confidence=result.confidence,
                    resolved_command=command_name,
                    queue_state="dispatch_ok" if dispatch_result is not None else "dispatch_failed",
                    detector_available=result.detector_available,
                )
                self.gesture_logger.log_command_event(
                    event_type="command_dispatch",
                    frame_id=frame_id,
                    command_sent=command_name,
                    command_block_reason="-",
                    command_ts_ms=command_ts,
                    ack_ts_ms=ack_ts,
                    gesture_pred=result.raw_gesture,
                    stable_gesture=result.stable_gesture,
                    confidence=result.confidence,
                    stable_ms=stable_ms,
                    threshold=threshold,
                    drone_state=self.current_drone_state(),
                    battery_pct=self.app_state.battery_pct,
                    height_cm=self.app_state.height_cm,
                )
                if dispatch_result is not None:
                    self._track_pending_motion(
                        frame_id=frame_id,
                        command_name=command_name,
                        command_ts_ms=command_ts,
                        ack_ts_ms=ack_ts,
                    )
                    return self.app_controller.gesture_controller.finalize_dispatch(command_name)
            else:
                gesture_debug_log(
                    "mainwindow.dispatch_blocked",
                    frame_id=frame_id,
                    raw_gesture=result.raw_gesture,
                    stable_gesture=result.stable_gesture,
                    confidence=result.confidence,
                    resolved_command=command_name,
                    queue_state=decision.block_reason,
                    detector_available=result.detector_available,
                )
                self.gesture_logger.log_command_event(
                    event_type="command_blocked",
                    frame_id=frame_id,
                    command_sent="-",
                    command_block_reason=decision.block_reason,
                    gesture_pred=result.raw_gesture,
                    stable_gesture=result.stable_gesture,
                    confidence=result.confidence,
                    stable_ms=stable_ms,
                    threshold=threshold,
                    drone_state=self.current_drone_state(),
                    battery_pct=self.app_state.battery_pct,
                    height_cm=self.app_state.height_cm,
                )
            return debug_state
        except ApiClientError as exc:
            gesture_debug_log(
                "mainwindow.api_error",
                raw_gesture="-",
                stable_gesture="-",
                confidence="-",
                resolved_command="-",
                queue_state=str(exc),
                detector_available=self.gesture_inference_service.is_detector_available(),
            )
            on_api_error(str(exc))
            return None
        except Exception:
            gesture_debug_log(
                "mainwindow.processing_error",
                raw_gesture="-",
                stable_gesture="-",
                confidence="-",
                resolved_command="-",
                queue_state="exception",
                detector_available=self.gesture_inference_service.is_detector_available(),
            )
            return None

    def apply_status_update(self, status_data: dict, state_data: object) -> None:
        previous_mode = self.app_state.mode
        previous_height = self.app_state.height_cm
        telemetry = self.telemetry_service.build_telemetry(status_data, state_data)
        self.app_state.mark_connected(telemetry.mode)
        self.app_state.update_from_telemetry(telemetry)
        self._maybe_log_motion_observed(previous_mode, previous_height)

    def apply_status_error(self, error_text: str) -> None:
        self.app_state.mark_disconnected(error_text)

    def apply_stream_status(self, text: str) -> None:
        self.app_state.set_stream_status(text)

    def call_api(self, action: Callable[[], Any], *, on_api_error: Callable[[str], None], suppress_noop: bool = False) -> Any:
        return self._call_api(action, on_api_error=on_api_error, suppress_noop=suppress_noop)

    def current_drone_state(self) -> str:
        return self.app_state.mode if self.app_state.mode else "--"

    def _call_api(
        self,
        action: Callable[[], Any],
        *,
        on_api_error: Callable[[str], None],
        suppress_noop: bool = False,
    ) -> Any:
        try:
            result = action()
            if result is None and suppress_noop:
                return None
            return result
        except ApiClientError as exc:
            on_api_error(str(exc))
            return None

    def _track_pending_motion(
        self,
        *,
        frame_id: int,
        command_name: str,
        command_ts_ms: int,
        ack_ts_ms: int | None,
    ) -> None:
        self._last_motion_probe = {
            "frame_id": frame_id,
            "command_name": command_name,
            "command_ts_ms": command_ts_ms,
            "ack_ts_ms": ack_ts_ms,
            "mode": self.app_state.mode,
            "height_cm": self.app_state.height_cm,
        }

    def _maybe_log_motion_observed(self, previous_mode: str, previous_height: int | None) -> None:
        probe = self._last_motion_probe
        if probe is None:
            return

        command_name = str(probe["command_name"])
        mode_changed = previous_mode != self.app_state.mode
        height_changed = previous_height != self.app_state.height_cm

        observed = False
        if command_name in {"up", "down"} and height_changed:
            observed = True
        elif command_name in {"takeoff", "land"} and (height_changed or mode_changed):
            observed = True
        elif command_name in {"forward", "back", "left", "right", "clockwise", "counter_clockwise"} and mode_changed:
            observed = True

        if not observed:
            return

        motion_ts_ms = int(time() * 1000)
        command_ts_ms = self._as_int(probe.get("command_ts_ms"))
        e2e_latency_ms = None
        if command_ts_ms is not None:
            e2e_latency_ms = max(0, motion_ts_ms - command_ts_ms)

        self.gesture_logger.log_motion_event(
            frame_id=int(probe["frame_id"]),
            command_sent=command_name,
            drone_state=self.current_drone_state(),
            battery_pct=self.app_state.battery_pct,
            height_cm=self.app_state.height_cm,
            command_ts_ms=command_ts_ms,
            ack_ts_ms=self._as_int(probe.get("ack_ts_ms")),
            drone_motion_ts_ms=motion_ts_ms,
            e2e_latency_ms=e2e_latency_ms,
        )
        self._last_motion_probe = None

    @staticmethod
    def _safe_stop_worker(worker: object | None) -> None:
        if worker is None:
            return
        stop = getattr(worker, "stop", None)
        if callable(stop):
            try:
                stop()
            except RuntimeError:
                pass

    @staticmethod
    def _safe_quit_thread(thread: QThread | None, timeout_ms: int) -> None:
        if thread is None:
            return
        if thread.isRunning():
            thread.quit()
            thread.wait(timeout_ms)

    @staticmethod
    def _as_int(value: object) -> int | None:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        return None

    @staticmethod
    def _as_float(value: object) -> float | None:
        if isinstance(value, bool):
            return float(value)
        if isinstance(value, (int, float)):
            return float(value)
        return None
