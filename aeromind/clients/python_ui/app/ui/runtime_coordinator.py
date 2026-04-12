from __future__ import annotations

from dataclasses import dataclass
from time import monotonic, time
from typing import Any, Callable

from PySide6.QtCore import QThread

from app.config import AppConfig
from app.controllers.app_controller import AppController
from app.models.app_state import AppState
from app.models.video_source import VideoSourceSpec
from app.services.api_client import ApiClientError
from app.services.gesture_inference_service import GestureInferenceService
from app.services.gesture_logger import GestureLogger
from app.services.telemetry_service import TelemetryService
from app.services.video_stream_service import VideoStreamService
from app.utils.logging_utils import gesture_debug_log
from app.workers.inference_worker import InferenceUpdate, InferenceWorker, LatestFrameBuffer
from app.workers.status_worker import StatusWorker
from app.workers.video_worker import VideoWorker


@dataclass(slots=True)
class _LatencyRecord:
    frame_id: int
    raw_gesture: str | None
    stable_gesture: str | None
    confidence: float | None
    t_frame_capture: int | None
    t_inference_done: int | None
    t_stable_ready: int | None
    t_command_dispatch_start: int | None
    t_command_dispatch_end: int | None
    api_roundtrip_ms: int | None
    vision_to_stable_ms: int | None
    stable_to_dispatch_ms: int | None
    total_client_pipeline_ms: int | None
    drone_motion_ts_ms: int | None = None


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
        self._started = False
        self._selected_video_mode: str | None = None
        self._last_hover_command_ts = 0.0
        self._last_seen_gesture_ts = 0.0
        self._last_logged_command_block_key: tuple[object, ...] | None = None
        self._last_logged_ready_key: tuple[object, ...] | None = None
        self._inference_frame_buffer = LatestFrameBuffer(self.config.inference_max_pending_frames)

        self.status_thread = QThread(parent)
        self.status_thread.setObjectName("status-thread")
        self.status_worker = StatusWorker(self.app_controller.api_client, self.config.status_refresh_ms)
        self.status_worker.moveToThread(self.status_thread)
        self.status_thread.started.connect(self.status_worker.start)
        self.status_worker.workerFinished.connect(self.status_thread.quit)
        self.status_thread.finished.connect(self.status_worker.deleteLater)
        self.status_thread.finished.connect(lambda: gesture_debug_log("thread.quit", thread="status"))
        self.status_worker.workerStarted.connect(lambda: gesture_debug_log("thread.worker_start", worker="status"))
        self.status_worker.workerFinished.connect(lambda: gesture_debug_log("thread.worker_finish_signal", worker="status"))

        self.video_thread = QThread(parent)
        self.video_thread.setObjectName("video-thread")
        self.video_worker = VideoWorker(
            self.video_service,
            self._video_source_for_mode(None),
            self.config.video_reconnect_delay_ms,
            read_interval_ms=self.config.video_read_interval_ms,
            drop_frames_on_reconnect=self.config.video_drop_frames_on_reconnect,
            inference_emit_interval_ms=self.config.gesture_inference_interval_ms(),
            perf_log_interval_ms=self.config.performance_log_interval_ms,
            frame_sink=self._inference_frame_buffer.submit,
        )
        self.video_worker.moveToThread(self.video_thread)
        self.video_thread.started.connect(self.video_worker.start)
        self.video_worker.workerFinished.connect(self.video_thread.quit)
        self.video_thread.finished.connect(self.video_worker.deleteLater)
        self.video_thread.finished.connect(lambda: gesture_debug_log("thread.quit", thread="video"))
        self.video_worker.workerStarted.connect(lambda: gesture_debug_log("thread.worker_start", worker="video"))
        self.video_worker.workerFinished.connect(lambda: gesture_debug_log("thread.worker_finish_signal", worker="video"))

        # Main video pipeline = sim/drone display stream.
        # Gesture pipeline = separate camera for inference.
        self.gesture_video_service = VideoStreamService(
            self.config.gesture_video_source(),
            prefer_ffmpeg=False,
            max_width=self.config.video_max_width,
            max_height=self.config.video_max_height,
        )
        self.gesture_video_thread = QThread(parent)
        self.gesture_video_thread.setObjectName("gesture-video-thread")
        self.gesture_video_worker = VideoWorker(
            self.gesture_video_service,
            self.config.gesture_video_source(),
            self.config.video_reconnect_delay_ms,
            read_interval_ms=self.config.video_read_interval_ms,
            drop_frames_on_reconnect=self.config.video_drop_frames_on_reconnect,
            inference_emit_interval_ms=self.config.gesture_inference_interval_ms(),
            perf_log_interval_ms=self.config.performance_log_interval_ms,
            frame_sink=self._inference_frame_buffer.submit,
        )
        self.gesture_video_worker.moveToThread(self.gesture_video_thread)
        self.gesture_video_thread.started.connect(self.gesture_video_worker.start)
        self.gesture_video_worker.workerFinished.connect(self.gesture_video_thread.quit)
        self.gesture_video_thread.finished.connect(self.gesture_video_worker.deleteLater)
        self.gesture_video_thread.finished.connect(lambda: gesture_debug_log("thread.quit", thread="gesture-video"))
        self.gesture_video_worker.workerStarted.connect(lambda: gesture_debug_log("thread.worker_start", worker="gesture-video"))
        self.gesture_video_worker.workerFinished.connect(lambda: gesture_debug_log("thread.worker_finish_signal", worker="gesture-video"))

        self.inference_thread = QThread(parent)
        self.inference_thread.setObjectName("inference-thread")
        self.inference_worker = InferenceWorker(
            self.gesture_inference_service,
            self._inference_frame_buffer,
            input_width=self.config.inference_input_width,
            input_height=self.config.inference_input_height,
            process_every_nth_frame=self.config.inference_process_every_nth_frame,
            perf_log_interval_ms=self.config.performance_log_interval_ms,
        )
        self.inference_worker.moveToThread(self.inference_thread)
        self.inference_thread.started.connect(self.inference_worker.start)
        self.inference_worker.workerFinished.connect(self.inference_thread.quit)
        self.inference_thread.finished.connect(self.inference_worker.deleteLater)
        self.inference_thread.finished.connect(lambda: gesture_debug_log("thread.quit", thread="inference"))
        self.inference_worker.workerStarted.connect(lambda: gesture_debug_log("thread.worker_start", worker="inference"))
        self.inference_worker.workerFinished.connect(lambda: gesture_debug_log("thread.worker_finish_signal", worker="inference"))

    def connect_workers(
        self,
        *,
        on_frame_ready: Callable[[object], None],
        on_inference_ready: Callable[[object], None],
        on_stream_status_changed: Callable[[str], None],
        on_status_updated: Callable[[dict, object, dict], None],
        on_status_error: Callable[[str], None],
    ) -> None:
        self.video_worker.frameReady.connect(on_frame_ready)
        self.inference_worker.inferenceReady.connect(on_inference_ready)
        self.video_worker.streamStatusChanged.connect(on_stream_status_changed)
        self.status_worker.statusUpdated.connect(on_status_updated)
        self.status_worker.statusError.connect(on_status_error)

    def start(self) -> None:
        if self._started:
            gesture_debug_log("thread.runtime_start_skipped", reason="already_started")
            return
        gesture_debug_log(
            "thread.runtime_start",
            status_thread_running=self.status_thread.isRunning(),
            video_thread_running=self.video_thread.isRunning(),
            gesture_video_thread_running=self.gesture_video_thread.isRunning(),
            inference_thread_running=self.inference_thread.isRunning(),
        )
        self.status_thread.start()
        self.video_thread.start()
        # Shared webcam/display worker also feeds inference frames; do not start a second webcam capture.
        self.inference_thread.start()
        self._started = True

    def stop(self) -> None:
        if not self._started and not self.status_thread.isRunning() and not self.video_thread.isRunning() and not self.gesture_video_thread.isRunning() and not self.inference_thread.isRunning():
            gesture_debug_log("thread.runtime_stop_skipped", reason="already_stopped")
            return
        gesture_debug_log("thread.runtime_stop_requested")
        self._safe_stop_worker(self.status_worker)
        self._safe_stop_worker(self.video_worker)
        # gesture_video_worker is intentionally not started; avoid opening the webcam twice.
        self._safe_stop_worker(self.inference_worker)
        self._safe_quit_thread(self.status_thread, 5000)
        self._safe_quit_thread(self.video_thread, 5000)
        # gesture_video_thread is intentionally not started.
        self._safe_quit_thread(self.inference_thread, 5000)
        self._started = False
        gesture_debug_log(
            "thread.cleanup_completed",
            status_thread_running=self.status_thread.isRunning(),
            video_thread_running=self.video_thread.isRunning(),
            gesture_video_thread_running=self.gesture_video_thread.isRunning(),
            inference_thread_running=self.inference_thread.isRunning(),
        )

    def reset_runtime_state(self) -> None:
        gesture_debug_log("thread.runtime_reset_state")
        self.gesture_inference_service.reset()
        self.app_controller.gesture_controller.disable()
        self.app_state.gesture_enabled = False
        self.app_controller.rc_controller.reset()
        self._selected_video_mode = None
        self._last_hover_command_ts = 0.0
        self._last_seen_gesture_ts = 0.0
        self._last_logged_command_block_key = None
        self._last_logged_ready_key = None
        self.clear_pending_gesture_frames()
        self.select_video_source(mode=None, reason="runtime_reset")
        self.video_service.close()
        self.app_state.reset_runtime_state()

    def clear_pending_gesture_frames(self) -> None:
        self._inference_frame_buffer.clear()

    def process_inference_update(
        self,
        update: InferenceUpdate,
        *,
        on_api_error: Callable[[str], None],
    ) -> dict[str, str | float | bool | None] | None:
        frame_id = self.gesture_logger.next_frame_id()
        try:
            result = update.result
            self.app_state.set_detector_state(
                ready=result.detector_status == "detector_ready",
                error_reason=result.detector_error if result.detector_status != "detector_ready" else None,
            )
            decision = self.app_controller.gesture_controller.evaluate_result(result)
            debug_state = decision.debug_state
            stable_ms = self._as_int(debug_state.get("stable_ms"))
            threshold = self._as_float(debug_state.get("threshold"))
            required_confidence = self._as_float(debug_state.get("required_confidence"))
            required_hits = self._as_int(debug_state.get("required_hits"))
            t_frame_capture = self._monotonic_to_ms(update.t_frame_capture)
            t_inference_done = self._monotonic_to_ms(update.t_inference_done)
            ui_shown = bool(result.raw_gesture or result.stable_gesture)
            if ui_shown:
                self._last_seen_gesture_ts = monotonic()
            gesture_debug_log(
                "gesture.pipeline_trace",
                frame_id=frame_id,
                raw_gesture=result.raw_gesture,
                stable_gesture=result.stable_gesture,
                confidence=result.confidence,
                resolved_command=decision.command_name,
                behavior_type=debug_state.get("behavior_type"),
                threshold=threshold,
                stable_ms=stable_ms,
                stable_hits=result.stable_hits,
                required_hits=required_hits,
                required_confidence=required_confidence,
                inference_queue_state=result.queue_state,
                controller_queue_state=debug_state.get("controller_queue_state"),
                block_reason=decision.block_reason,
                latched_terminal_command=debug_state.get("latched_terminal_command"),
                terminal_lock_active=debug_state.get("terminal_lock_active"),
                ui_shown=ui_shown,
                dispatch_allowed=decision.dispatch_allowed,
                dispatch_attempted=False,
                freshness_ms=update.freshness_ms,
                processing_ms=f"{update.processing_ms:.2f}",
                inference_shape=update.inference_shape,
                detector_available=result.detector_available,
            )
            command_name = decision.command_name
            # The gesture becomes "stable ready" once inference has produced an actionable
            # command candidate and its queue state is accepted for dispatch.
            actionable_ready = bool(command_name) and result.queue_state in {"ready", "debug_bypass"}
            latency_ready = self._build_latency_record(
                frame_id=frame_id,
                result=result,
                t_frame_capture=t_frame_capture,
                t_inference_done=t_inference_done,
                t_stable_ready=t_inference_done if actionable_ready else None,
                t_command_dispatch_start=None,
                t_command_dispatch_end=None,
                drone_motion_ts_ms=None,
            )
            self._maybe_log_gesture_ready(
                result=result,
                decision=decision,
                debug_state=debug_state,
                threshold=threshold,
                required_hits=required_hits,
                required_confidence=required_confidence,
                latency=latency_ready,
            )
            if decision.dispatch_allowed:
                assert command_name is not None
                dispatch_reason = "-"
                if command_name in {"hover", "stop"}:
                    dispatch_reason = (
                        self._as_text(debug_state.get("pending_movement_stop_reason"))
                        or decision.block_reason
                        or "-"
                    )
                # Timestamp taken immediately before the client enters the API dispatch call.
                dispatch_started_at = monotonic()
                dispatch_start_ms = self._monotonic_to_ms(dispatch_started_at)
                command_ts = int(time() * 1000)
                gesture_debug_log(
                    "mainwindow.dispatch_attempt",
                    frame_id=frame_id,
                    raw_gesture=result.raw_gesture,
                    stable_gesture=result.stable_gesture,
                    confidence=result.confidence,
                    resolved_command=command_name,
                    threshold=threshold,
                    stable_ms=stable_ms,
                    block_reason=dispatch_reason,
                    dispatch_attempted=True,
                    detector_available=result.detector_available,
                )
                dispatch_result = self._call_api(
                    lambda: self.app_controller.command_controller.execute_gesture_command(command_name),
                    on_api_error=on_api_error,
                    command_status="sent",
                )
                # Timestamp taken immediately after the API call returns to the client.
                dispatch_finished_at = monotonic()
                dispatch_end_ms = self._monotonic_to_ms(dispatch_finished_at)
                ack_ts = int(time() * 1000) if dispatch_result is not None else None
                latency_dispatch = self._build_latency_record(
                    frame_id=frame_id,
                    result=result,
                    t_frame_capture=t_frame_capture,
                    t_inference_done=t_inference_done,
                    t_stable_ready=t_inference_done,
                    t_command_dispatch_start=dispatch_start_ms,
                    t_command_dispatch_end=dispatch_end_ms,
                    drone_motion_ts_ms=None,
                )
                gesture_debug_log(
                    "mainwindow.dispatch_result",
                    frame_id=frame_id,
                    raw_gesture=result.raw_gesture,
                    stable_gesture=result.stable_gesture,
                    confidence=result.confidence,
                    resolved_command=command_name,
                    threshold=threshold,
                    stable_ms=stable_ms,
                    queue_state="dispatch_ok" if dispatch_result is not None else "dispatch_failed",
                    block_reason=dispatch_reason if dispatch_result is not None else "api_dispatch_failed",
                    detector_available=result.detector_available,
                    api_roundtrip_ms=latency_dispatch.api_roundtrip_ms,
                    total_client_pipeline_ms=latency_dispatch.total_client_pipeline_ms,
                )
                self.gesture_logger.log_command_event(
                    event_type="command_dispatch",
                    frame_id=frame_id,
                    gesture_pred=result.raw_gesture,
                    stable_gesture=result.stable_gesture,
                    confidence=result.confidence,
                    stable_ms=stable_ms,
                    stable_hits=result.stable_hits,
                    t_frame_capture=latency_dispatch.t_frame_capture,
                    t_inference_done=latency_dispatch.t_inference_done,
                    t_stable_ready=latency_dispatch.t_stable_ready,
                    t_command_dispatch_start=latency_dispatch.t_command_dispatch_start,
                    t_command_dispatch_end=latency_dispatch.t_command_dispatch_end,
                    api_roundtrip_ms=latency_dispatch.api_roundtrip_ms,
                    vision_to_stable_ms=latency_dispatch.vision_to_stable_ms,
                    stable_to_dispatch_ms=latency_dispatch.stable_to_dispatch_ms,
                    total_client_pipeline_ms=latency_dispatch.total_client_pipeline_ms,
                    resolved_command=command_name,
                    dispatch_allowed=True,
                    command_sent=command_name,
                    command_block_reason=dispatch_reason,
                    command_ts_ms=command_ts,
                    ack_ts_ms=ack_ts,
                    threshold=threshold,
                    inference_queue_state=result.queue_state,
                    controller_queue_state=self._as_text(debug_state.get("controller_queue_state")),
                    required_hits=required_hits,
                    required_confidence=required_confidence,
                    drone_state=self.current_drone_state(),
                    battery_pct=self.app_state.battery_pct,
                    height_cm=self.app_state.height_cm,
                )
                self._emit_latency_console(
                    event_type="command_dispatch",
                    latency=latency_dispatch,
                    command_name=command_name,
                    stable_ms=stable_ms,
                    block_reason=dispatch_reason,
                )
                self._last_logged_command_block_key = None
                if dispatch_result is not None:
                    self._track_pending_motion(
                        frame_id=frame_id,
                        command_name=command_name,
                        command_ts_ms=command_ts,
                        ack_ts_ms=ack_ts,
                        latency=latency_dispatch,
                    )
                    return self.app_controller.gesture_controller.finalize_dispatch(command_name)
            else:
                self.app_state.set_command_status(status="blocked", error=decision.block_reason)
                gesture_debug_log(
                    "mainwindow.dispatch_blocked",
                    frame_id=frame_id,
                    raw_gesture=result.raw_gesture,
                    stable_gesture=result.stable_gesture,
                    confidence=result.confidence,
                    resolved_command=command_name,
                    threshold=threshold,
                    stable_ms=stable_ms,
                    queue_state=debug_state.get("controller_queue_state"),
                    block_reason=decision.block_reason,
                    latched_terminal_command=debug_state.get("latched_terminal_command"),
                    terminal_lock_active=debug_state.get("terminal_lock_active"),
                    ui_shown=ui_shown,
                    dispatch_attempted=False,
                    detector_available=result.detector_available,
                )
                if self._should_log_command_blocked(
                    result=result,
                    decision=decision,
                    debug_state=debug_state,
                ):
                    latency_blocked = self._build_latency_record(
                        frame_id=frame_id,
                        result=result,
                        t_frame_capture=t_frame_capture,
                        t_inference_done=t_inference_done,
                        t_stable_ready=t_inference_done if actionable_ready else None,
                        t_command_dispatch_start=None,
                        t_command_dispatch_end=None,
                        drone_motion_ts_ms=None,
                    )
                    self.gesture_logger.log_command_event(
                        event_type="command_blocked",
                        frame_id=frame_id,
                        gesture_pred=result.raw_gesture,
                        stable_gesture=result.stable_gesture,
                        confidence=result.confidence,
                        stable_ms=stable_ms,
                        stable_hits=result.stable_hits,
                        t_frame_capture=latency_blocked.t_frame_capture,
                        t_inference_done=latency_blocked.t_inference_done,
                        t_stable_ready=latency_blocked.t_stable_ready,
                        t_command_dispatch_start=latency_blocked.t_command_dispatch_start,
                        t_command_dispatch_end=latency_blocked.t_command_dispatch_end,
                        api_roundtrip_ms=latency_blocked.api_roundtrip_ms,
                        vision_to_stable_ms=latency_blocked.vision_to_stable_ms,
                        stable_to_dispatch_ms=latency_blocked.stable_to_dispatch_ms,
                        total_client_pipeline_ms=latency_blocked.total_client_pipeline_ms,
                        resolved_command=command_name,
                        dispatch_allowed=False,
                        command_sent="-",
                        command_block_reason=decision.block_reason,
                        threshold=threshold,
                        inference_queue_state=result.queue_state,
                        controller_queue_state=self._as_text(debug_state.get("controller_queue_state")),
                        required_hits=required_hits,
                        required_confidence=required_confidence,
                        drone_state=self.current_drone_state(),
                        battery_pct=self.app_state.battery_pct,
                        height_cm=self.app_state.height_cm,
                    )
                    self._emit_latency_console(
                        event_type="command_blocked",
                        latency=latency_blocked,
                        command_name=command_name,
                        stable_ms=stable_ms,
                        block_reason=decision.block_reason,
                    )
                self._maybe_auto_hover(
                    result=result,
                    decision=decision,
                    frame_id=frame_id,
                    on_api_error=on_api_error,
                )
            return debug_state
        except ApiClientError as exc:
            gesture_debug_log(
                "mainwindow.api_error",
                frame_id=frame_id,
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
                frame_id=frame_id,
                raw_gesture="-",
                stable_gesture="-",
                confidence="-",
                resolved_command="-",
                queue_state="exception",
                detector_available=self.gesture_inference_service.is_detector_available(),
            )
            return None

    def apply_status_update(self, status_data: dict, state_data: object, diag_data: dict) -> None:
        previous_mode = self.app_state.mode
        previous_height = self.app_state.height_cm
        telemetry = self.telemetry_service.build_telemetry(status_data, state_data, diag_data)
        self.app_state.mark_connected(telemetry.mode, sdk_mode_ready=telemetry.sdk_mode_ready)
        self.app_state.update_from_telemetry(telemetry)
        self.select_video_source(mode=telemetry.mode, reason="status_update")
        self._maybe_log_motion_observed(previous_mode, previous_height)

    def apply_status_error(self, error_text: str) -> None:
        self.app_state.mark_disconnected(error_text)

    def apply_stream_status(self, text: str) -> None:
        self.app_state.set_stream_status(text)

    def call_api(self, action: Callable[[], Any], *, on_api_error: Callable[[str], None], suppress_noop: bool = False) -> Any:
        return self._call_api(action, on_api_error=on_api_error, suppress_noop=suppress_noop)

    def start_sim_mode(self, *, on_api_error: Callable[[str], None]) -> Any:
        result = self._call_api(self.app_controller.command_controller.start_sim, on_api_error=on_api_error)
        if result is not None:
            self.select_video_source(mode="sim", reason="start_sim")
        return result

    def start_drone_mode(self, *, on_api_error: Callable[[str], None]) -> Any:
        result = self._call_api(self.app_controller.command_controller.start_drone, on_api_error=on_api_error)
        if result is not None:
            self.select_video_source(mode="drone", reason="start_drone")
        return result

    def current_drone_state(self) -> str:
        return self.app_state.mode if self.app_state.mode else "--"

    def select_video_source(self, *, mode: str | None, reason: str) -> None:
        normalized_mode = self._normalize_mode(mode)
        source = self._video_source_for_mode(normalized_mode)
        if source is None:
            return
        if self._selected_video_mode == normalized_mode:
            return
        self._selected_video_mode = normalized_mode
        gesture_debug_log(
            "video.mode_selected",
            mode=normalized_mode or "--",
            reason=reason,
            source_kind=source.kind,
            source_value=source.value,
            source_label=source.label,
        )
        self.video_worker.set_source(source, mode=normalized_mode, reason=reason)

    def _maybe_auto_hover(
        self,
        *,
        result: Any,
        decision: Any,
        frame_id: int,
        on_api_error: Callable[[str], None],
    ) -> None:
        if not self.app_controller.gesture_controller.is_enabled():
            return
        if self.app_state.mode not in {"drone", "sim"}:
            return
        if result.raw_gesture or result.stable_gesture:
            return

        now = monotonic()
        idle_ms = int((now - self._last_seen_gesture_ts) * 1000.0) if self._last_seen_gesture_ts > 0 else self.config.gesture_idle_hover_ms
        if idle_ms < self.config.gesture_idle_hover_ms:
            return
        if (now - self._last_hover_command_ts) * 1000.0 < self.config.gesture_hover_command_cooldown_ms:
            return

        # Do not spam the drone with repeated stop commands while no gesture is visible.
        # Tello naturally holds position after a completed movement command, so waiting here keeps it hovering.
        self.app_state.set_command_status(status="hover", error=None)
        self._last_hover_command_ts = now
        gesture_debug_log(
            "gesture.auto_hover",
            frame_id=frame_id,
            raw_gesture=result.raw_gesture,
            stable_gesture=result.stable_gesture,
            confidence=result.confidence,
            resolved_command=decision.command_name,
            block_reason=decision.block_reason,
            idle_ms=idle_ms,
            sent=False,
            mode="passive_hover",
        )

    def _should_log_command_blocked(
        self,
        *,
        result: Any,
        decision: Any,
        debug_state: dict[str, str | float | bool | None],
    ) -> bool:
        key = (
            decision.command_name or "-",
            result.raw_gesture or "-",
            result.stable_gesture or "-",
            result.queue_state or "-",
            self._as_text(debug_state.get("controller_queue_state")) or "-",
            decision.block_reason or "-",
        )
        should_log = key != self._last_logged_command_block_key
        if should_log:
            self._last_logged_command_block_key = key
        return should_log

    def _maybe_log_gesture_ready(
        self,
        *,
        result: Any,
        decision: Any,
        debug_state: dict[str, str | float | bool | None],
        threshold: float | None,
        required_hits: int | None,
        required_confidence: float | None,
        latency: _LatencyRecord,
    ) -> None:
        key = self._gesture_ready_key(result=result, decision=decision)
        if key is None:
            self._last_logged_ready_key = None
            return
        if key == self._last_logged_ready_key:
            return
        self._last_logged_ready_key = key
        self.gesture_logger.log_command_event(
            event_type="gesture_ready",
            frame_id=latency.frame_id,
            gesture_pred=result.raw_gesture,
            stable_gesture=result.stable_gesture,
            confidence=result.confidence,
            stable_ms=self._as_int(debug_state.get("stable_ms")),
            stable_hits=result.stable_hits,
            t_frame_capture=latency.t_frame_capture,
            t_inference_done=latency.t_inference_done,
            t_stable_ready=latency.t_stable_ready,
            t_command_dispatch_start=None,
            t_command_dispatch_end=None,
            api_roundtrip_ms=None,
            vision_to_stable_ms=latency.vision_to_stable_ms,
            stable_to_dispatch_ms=None,
            total_client_pipeline_ms=latency.total_client_pipeline_ms,
            threshold=threshold,
            resolved_command=decision.command_name,
            dispatch_allowed=decision.dispatch_allowed,
            command_sent="-",
            command_block_reason="-",
            inference_queue_state=result.queue_state,
            controller_queue_state=self._as_text(debug_state.get("controller_queue_state")),
            required_hits=required_hits,
            required_confidence=required_confidence,
            drone_state=self.current_drone_state(),
            battery_pct=self.app_state.battery_pct,
            height_cm=self.app_state.height_cm,
        )
        self._emit_latency_console(
            event_type="gesture_ready",
            latency=latency,
            command_name=decision.command_name,
            stable_ms=self._as_int(debug_state.get("stable_ms")),
            block_reason="-",
        )

    @staticmethod
    def _gesture_ready_key(*, result: Any, decision: Any) -> tuple[object, ...] | None:
        if not decision.command_name or result.queue_state not in {"ready", "debug_bypass"}:
            return None
        return (
            decision.command_name,
            result.stable_gesture or "-",
            result.queue_state,
        )

    def _build_latency_record(
        self,
        *,
        frame_id: int,
        result: Any,
        t_frame_capture: int | None,
        t_inference_done: int | None,
        t_stable_ready: int | None,
        t_command_dispatch_start: int | None,
        t_command_dispatch_end: int | None,
        drone_motion_ts_ms: int | None,
    ) -> _LatencyRecord:
        vision_to_stable_ms = self._duration_ms(t_frame_capture, t_stable_ready)
        stable_to_dispatch_ms = self._duration_ms(t_stable_ready, t_command_dispatch_start)
        api_roundtrip_ms = self._duration_ms(t_command_dispatch_start, t_command_dispatch_end)
        total_client_pipeline_ms = self._duration_ms(t_frame_capture, t_command_dispatch_end)
        if total_client_pipeline_ms is None:
            total_client_pipeline_ms = self._duration_ms(t_frame_capture, t_stable_ready)
        if total_client_pipeline_ms is None:
            total_client_pipeline_ms = self._duration_ms(t_frame_capture, t_inference_done)
        return _LatencyRecord(
            frame_id=frame_id,
            raw_gesture=result.raw_gesture,
            stable_gesture=result.stable_gesture,
            confidence=result.confidence,
            t_frame_capture=t_frame_capture,
            t_inference_done=t_inference_done,
            t_stable_ready=t_stable_ready,
            t_command_dispatch_start=t_command_dispatch_start,
            t_command_dispatch_end=t_command_dispatch_end,
            api_roundtrip_ms=api_roundtrip_ms,
            vision_to_stable_ms=vision_to_stable_ms,
            stable_to_dispatch_ms=stable_to_dispatch_ms,
            total_client_pipeline_ms=total_client_pipeline_ms,
            drone_motion_ts_ms=drone_motion_ts_ms,
        )

    def _with_motion_latency(self, latency: object, motion_monotonic_ms: int | None) -> _LatencyRecord | None:
        if not isinstance(latency, _LatencyRecord):
            return None
        total_client_pipeline_ms = latency.total_client_pipeline_ms
        if motion_monotonic_ms is not None and latency.t_frame_capture is not None:
            total_client_pipeline_ms = max(0, motion_monotonic_ms - latency.t_frame_capture)
        return _LatencyRecord(
            frame_id=latency.frame_id,
            raw_gesture=latency.raw_gesture,
            stable_gesture=latency.stable_gesture,
            confidence=latency.confidence,
            t_frame_capture=latency.t_frame_capture,
            t_inference_done=latency.t_inference_done,
            t_stable_ready=latency.t_stable_ready,
            t_command_dispatch_start=latency.t_command_dispatch_start,
            t_command_dispatch_end=latency.t_command_dispatch_end,
            api_roundtrip_ms=latency.api_roundtrip_ms,
            vision_to_stable_ms=latency.vision_to_stable_ms,
            stable_to_dispatch_ms=latency.stable_to_dispatch_ms,
            total_client_pipeline_ms=total_client_pipeline_ms,
            drone_motion_ts_ms=motion_monotonic_ms,
        )

    @staticmethod
    def _emit_latency_console(
        *,
        event_type: str,
        latency: _LatencyRecord,
        command_name: str | None,
        stable_ms: int | None,
        block_reason: str,
    ) -> None:
        print(
            "[LATENCY] "
            f"event={event_type} "
            f"frame_id={latency.frame_id} "
            f"gesture={latency.stable_gesture or latency.raw_gesture or '-'} "
            f"command={command_name or '-'} "
            f"stable_ms={stable_ms if stable_ms is not None else '-'} "
            f"vision_to_stable={latency.vision_to_stable_ms if latency.vision_to_stable_ms is not None else '-'} "
            f"dispatch={latency.stable_to_dispatch_ms if latency.stable_to_dispatch_ms is not None else '-'} "
            f"api={latency.api_roundtrip_ms if latency.api_roundtrip_ms is not None else '-'} "
            f"total={latency.total_client_pipeline_ms if latency.total_client_pipeline_ms is not None else '-'} "
            f"block_reason={block_reason or '-'}",
            flush=True,
        )

    @staticmethod
    def _duration_ms(start_ms: int | None, end_ms: int | None) -> int | None:
        if start_ms is None or end_ms is None:
            return None
        return max(0, end_ms - start_ms)

    @staticmethod
    def _monotonic_to_ms(value: float | None) -> int | None:
        if value is None or value <= 0.0:
            return None
        return int(value * 1000.0)

    def _call_api(
        self,
        action: Callable[[], Any],
        *,
        on_api_error: Callable[[str], None],
        suppress_noop: bool = False,
        command_status: str = "sent",
    ) -> Any:
        try:
            result = action()
            if result is None and suppress_noop:
                return None
            self.app_state.set_command_status(status=command_status, error=None)
            return result
        except ApiClientError as exc:
            self.app_state.set_command_status(status="failed", error=str(exc))
            on_api_error(str(exc))
            return None

    def _track_pending_motion(
        self,
        *,
        frame_id: int,
        command_name: str,
        command_ts_ms: int,
        ack_ts_ms: int | None,
        latency: _LatencyRecord,
    ) -> None:
        self._last_motion_probe = {
            "frame_id": frame_id,
            "command_name": command_name,
            "command_ts_ms": command_ts_ms,
            "ack_ts_ms": ack_ts_ms,
            "mode": self.app_state.mode,
            "height_cm": self.app_state.height_cm,
            "latency": latency,
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
        elif command_name in {"forward", "back", "left", "right", "clockwise", "counter_clockwise", "rotate_right", "rotate_left"} and mode_changed:
            observed = True

        if not observed:
            return

        motion_ts_ms = int(time() * 1000)
        motion_monotonic_ms = self._monotonic_to_ms(monotonic())
        command_ts_ms = self._as_int(probe.get("command_ts_ms"))
        e2e_latency_ms = None
        if command_ts_ms is not None:
            e2e_latency_ms = max(0, motion_ts_ms - command_ts_ms)
        latency = self._with_motion_latency(probe.get("latency"), motion_monotonic_ms)

        self.gesture_logger.log_motion_event(
            frame_id=int(probe["frame_id"]),
            command_sent=command_name,
            drone_state=self.current_drone_state(),
            battery_pct=self.app_state.battery_pct,
            height_cm=self.app_state.height_cm,
            t_frame_capture=latency.t_frame_capture if latency is not None else None,
            t_inference_done=latency.t_inference_done if latency is not None else None,
            t_stable_ready=latency.t_stable_ready if latency is not None else None,
            t_command_dispatch_start=latency.t_command_dispatch_start if latency is not None else None,
            t_command_dispatch_end=latency.t_command_dispatch_end if latency is not None else None,
            api_roundtrip_ms=latency.api_roundtrip_ms if latency is not None else None,
            vision_to_stable_ms=latency.vision_to_stable_ms if latency is not None else None,
            stable_to_dispatch_ms=latency.stable_to_dispatch_ms if latency is not None else None,
            total_client_pipeline_ms=latency.total_client_pipeline_ms if latency is not None else None,
            command_ts_ms=command_ts_ms,
            ack_ts_ms=self._as_int(probe.get("ack_ts_ms")),
            drone_motion_ts_ms=motion_ts_ms,
            e2e_latency_ms=e2e_latency_ms,
        )
        if latency is not None:
            self._emit_latency_console(
                event_type="motion_observed",
                latency=latency,
                command_name=command_name,
                stable_ms=None,
                block_reason="-",
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
            except RuntimeError as exc:
                gesture_debug_log("thread.worker_stop_failed", worker=type(worker).__name__, error=repr(exc))

    @staticmethod
    def _safe_quit_thread(thread: QThread | None, timeout_ms: int) -> None:
        if thread is None:
            return
        if not thread.isRunning():
            return
        gesture_debug_log("thread.quit_requested", thread=thread.objectName() or "unnamed", timeout_ms=timeout_ms)
        if thread.isRunning():
            thread.quit()
            if not thread.wait(timeout_ms):
                gesture_debug_log("thread.wait_timeout", thread=thread.objectName() or "unnamed", timeout_ms=timeout_ms)
                thread.requestInterruption()
                if not thread.wait(1000):
                    gesture_debug_log("thread.terminate_requested", thread=thread.objectName() or "unnamed")
                    thread.terminate()
                    thread.wait(1000)
            else:
                gesture_debug_log("thread.wait_completed", thread=thread.objectName() or "unnamed", timeout_ms=timeout_ms)

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

    @staticmethod
    def _as_text(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _video_source_for_mode(self, mode: str | None) -> VideoSourceSpec | None:
        normalized_mode = self._normalize_mode(mode)
        # The gesture camera is a separate pipeline; the main VideoWorker should follow
        # the active sim/drone video transport, not the gesture webcam source.
        if normalized_mode == "sim":
            return self.config.sim_video_source()
        if normalized_mode == "drone":
            return self.config.drone_video_source()
        return self.config.drone_video_source()

    @staticmethod
    def _normalize_mode(mode: str | None) -> str | None:
        if mode is None:
            return None
        normalized = str(mode).strip().lower()
        if not normalized or normalized == "--":
            return None
        return normalized
