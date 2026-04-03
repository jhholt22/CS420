from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

from app.config import AppConfig
from app.controllers.app_controller import AppController
from app.models.app_state import AppState
from app.services.gesture_inference_service import GestureInferenceService
from app.services.gesture_logger import GestureLogger
from app.services.startup_smoke_check import StartupSmokeCheckService
from app.services.telemetry_service import TelemetryService
from app.services.video_stream_service import VideoStreamService
from app.ui.panels.gesture_debug_panel import GestureDebugPanel
from app.ui.panels.hud_top_bar import HudTopBar
from app.ui.runtime_coordinator import ClientRuntimeCoordinator
from app.ui.panels.video_surface import VideoSurface
from app.ui.widgets.flight_action_cluster import FlightActionCluster
from app.ui.widgets.virtual_stick import VirtualStick
from app.utils.logging_utils import gesture_debug_log


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AeroMind Control Center")
        self.setMinimumSize(1200, 800)
        self._is_shutting_down = False

        central_widget = QWidget(self)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.video_surface = VideoSurface(central_widget)
        layout.addWidget(self.video_surface)

        self.hud_top_bar = HudTopBar(self.video_surface.overlay_container)
        self.left_stick = VirtualStick("Yaw / Up-Down", size=216, parent=self.video_surface.overlay_container)
        self.right_stick = VirtualStick("Left-Right / Forward-Back", size=216, parent=self.video_surface.overlay_container)
        self.flight_action_cluster = FlightActionCluster(self.video_surface.overlay_container)
        self.gesture_debug_panel = GestureDebugPanel(self.video_surface.overlay_container)

        self.hud_top_bar.raise_()
        self.left_stick.raise_()
        self.right_stick.raise_()
        self.flight_action_cluster.raise_()
        self.gesture_debug_panel.raise_()

        self.setCentralWidget(central_widget)

        self.config = AppConfig()
        self.app_controller = AppController(self.config)
        self.app_state = AppState()
        self.gesture_inference_service = GestureInferenceService()
        self.gesture_logger = GestureLogger(flush_every_rows=self.config.gesture_log_flush_rows)
        self.gesture_logger.set_session_context(
            participant_id="P001",
            lighting="unknown",
            background="unknown",
            distance_m="",
            notes="",
        )
        self.gesture_debug_panel.set_session_context(**self.gesture_logger.get_session_context())
        self.telemetry_service = TelemetryService()
        self.video_service = VideoStreamService(
            self.config.drone_video_source(),
            prefer_ffmpeg=self.config.video_backend_prefer_ffmpeg,
            max_width=self.config.video_max_width,
            max_height=self.config.video_max_height,
        )
        self.startup_smoke_check = StartupSmokeCheckService(
            config=self.config,
            api_client=self.app_controller.api_client,
            gesture_inference_service=self.gesture_inference_service,
            video_stream_service=self.video_service,
        )
        self.runtime = ClientRuntimeCoordinator(
            parent=self,
            config=self.config,
            app_controller=self.app_controller,
            app_state=self.app_state,
            gesture_inference_service=self.gesture_inference_service,
            gesture_logger=self.gesture_logger,
            telemetry_service=self.telemetry_service,
            video_service=self.video_service,
        )
        self._connect_worker_signals()
        self._gesture_inference_timer = QTimer(self)
        self._gesture_inference_timer.setInterval(self.config.gesture_inference_interval_ms())
        self._gesture_inference_timer.timeout.connect(self._process_pending_gesture_frame)

        self._apply_hud_defaults()
        self._apply_debug_defaults()
        self._wire_interactions()
        self._register_label_shortcuts()
        self._layout_overlays()
        self._run_startup_smoke_check()

        self.runtime.start()
        self._gesture_inference_timer.start()

    def _connect_worker_signals(self) -> None:
        self.runtime.connect_workers(
            on_frame_ready=self.video_surface.set_video_pixmap,
            on_raw_frame_ready=self._on_raw_frame_ready,
            on_stream_status_changed=self._on_stream_status_changed,
            on_status_updated=self._on_status_updated,
            on_status_error=self._on_status_error,
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "hud_top_bar"):
            self._layout_overlays()

    def closeEvent(self, event) -> None:
        if self._is_shutting_down:
            event.accept()
            return

        self._is_shutting_down = True
        gesture_debug_log("thread.window_close_started")
        self._gesture_inference_timer.stop()
        self.runtime.stop()
        self.runtime.reset_runtime_state()
        self.gesture_logger.close()
        self._sync_ui_from_state()
        gesture_debug_log("thread.window_close_completed")
        event.accept()
        super().closeEvent(event)

    def _layout_overlays(self) -> None:
        edge_margin = 32
        top_margin = 18
        bottom_margin = 34
        stack_spacing = 18

        surface_width = self.video_surface.width()
        surface_height = self.video_surface.height()

        top_bar_width = max(760, surface_width - (edge_margin * 2))
        self.hud_top_bar.setGeometry(edge_margin, top_margin, top_bar_width, 44)

        left_size = self.left_stick.size()
        right_size = self.right_stick.size()
        left_y = surface_height - left_size.height() - bottom_margin
        right_y = surface_height - right_size.height() - bottom_margin

        self.left_stick.move(edge_margin, left_y)
        self.right_stick.move(surface_width - right_size.width() - edge_margin, right_y)

        cluster_size = self.flight_action_cluster.sizeHint()
        cluster_x = surface_width - cluster_size.width() - edge_margin
        cluster_y = right_y - cluster_size.height() - stack_spacing
        cluster_min_y = self.hud_top_bar.y() + self.hud_top_bar.height() + stack_spacing
        cluster_y = max(cluster_min_y, cluster_y)
        self.flight_action_cluster.setGeometry(
            cluster_x,
            cluster_y,
            cluster_size.width(),
            cluster_size.height(),
        )

        debug_size = self.gesture_debug_panel.sizeHint()
        debug_x = surface_width - debug_size.width() - edge_margin
        debug_y = cluster_y - debug_size.height() - stack_spacing
        debug_min_y = self.hud_top_bar.y() + self.hud_top_bar.height() + stack_spacing
        debug_y = max(debug_min_y, debug_y)
        self.gesture_debug_panel.setGeometry(
            debug_x,
            debug_y,
            debug_size.width(),
            debug_size.height(),
        )

    def _apply_hud_defaults(self) -> None:
        self.app_state.connected = False
        self.app_state.mode = "--"
        self.app_state.battery_pct = None
        self.app_state.height_cm = None
        self.app_state.set_stream_status("No Signal")
        self._sync_ui_from_state()

    def _run_startup_smoke_check(self) -> None:
        summary = self.startup_smoke_check.run()
        self.app_state.set_startup_summary(summary)
        self._sync_ui_from_state()

    def _apply_debug_defaults(self) -> None:
        self.app_state.gesture_enabled = self.app_controller.gesture_controller.is_enabled()
        self.app_controller.gesture_controller.reset()
        self.flight_action_cluster.set_rc_interval_value(self.app_controller.rc_controller.send_interval_ms)
        self._sync_ui_from_state()

    def _wire_interactions(self) -> None:
        self.flight_action_cluster.startSimClicked.connect(self._on_start_sim_clicked)
        self.flight_action_cluster.startDroneClicked.connect(self._on_start_drone_clicked)
        self.flight_action_cluster.stopClicked.connect(self._on_stop_clicked)
        self.flight_action_cluster.takeoffClicked.connect(self._on_takeoff_clicked)
        self.flight_action_cluster.landClicked.connect(self._on_land_clicked)
        self.flight_action_cluster.emergencyClicked.connect(self._on_emergency_clicked)
        self.flight_action_cluster.rcIntervalChanged.connect(self._on_rc_interval_changed)
        self.gesture_debug_panel.gestureToggleClicked.connect(self._on_gesture_toggle_clicked)
        self.gesture_debug_panel.sessionStartClicked.connect(self._on_start_session_clicked)
        self.gesture_debug_panel.sessionEndClicked.connect(self._on_end_session_clicked)
        self.gesture_debug_panel.clearLabelClicked.connect(self._on_clear_label_clicked)

        self.left_stick.valueChanged.connect(self._on_left_stick_changed)
        self.right_stick.valueChanged.connect(self._on_right_stick_changed)
        self.left_stick.stickReleased.connect(self._on_stick_released)
        self.right_stick.stickReleased.connect(self._on_stick_released)

    def _register_label_shortcuts(self) -> None:
        label_bindings = {
            "0": "no_label",
            "1": "open_palm",
            "2": "fist",
            "3": "thumbs_up",
            "4": "thumbs_down",
            "5": "point_up",
        }
        self._label_shortcuts: list[QShortcut] = []
        for key, label in label_bindings.items():
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(lambda selected=label: self._set_current_gesture_label(selected))
            self._label_shortcuts.append(shortcut)

    def _set_current_gesture_label(self, label: str) -> None:
        self.gesture_logger.set_current_label(label)
        self.gesture_logger.log_label_change(notes=f"label={self.gesture_logger.get_current_label()}")
        self._sync_gesture_panel_from_state()

    def _on_clear_label_clicked(self) -> None:
        self.gesture_logger.clear_current_label()
        self.gesture_logger.log_label_change(notes="label_cleared")
        self._sync_gesture_panel_from_state()

    def _on_start_session_clicked(self) -> None:
        self._apply_session_context_from_panel()
        self.gesture_logger.start_session()
        self.gesture_logger.log_session_event(event_type="session_start", notes="session_active")
        self._sync_gesture_panel_from_state()

    def _on_end_session_clicked(self) -> None:
        self._apply_session_context_from_panel()
        self.gesture_logger.log_session_event(event_type="session_end", notes="session_inactive")
        self.gesture_logger.end_session()
        self._sync_gesture_panel_from_state()

    def _apply_session_context_from_panel(self) -> None:
        context = self.gesture_debug_panel.get_session_context()
        self.gesture_logger.set_session_context(
            participant_id=context["participant_id"],
            lighting=context["lighting"],
            background=context["background"],
            distance_m=context["distance_m"],
            notes=context["notes"],
        )

    def _on_start_sim_clicked(self) -> None:
        self.runtime.start_sim_mode(on_api_error=self._on_status_error)

    def _on_start_drone_clicked(self) -> None:
        self.runtime.start_drone_mode(on_api_error=self._on_status_error)

    def _on_stop_clicked(self) -> None:
        self.runtime.call_api(self.app_controller.command_controller.stop, on_api_error=self._on_status_error)

    def _on_takeoff_clicked(self) -> None:
        self.runtime.call_api(self.app_controller.command_controller.takeoff, on_api_error=self._on_status_error)

    def _on_land_clicked(self) -> None:
        self.runtime.call_api(self.app_controller.command_controller.land, on_api_error=self._on_status_error)

    def _on_emergency_clicked(self) -> None:
        self.runtime.call_api(self.app_controller.command_controller.emergency, on_api_error=self._on_status_error)

    def _on_rc_interval_changed(self, value: int) -> None:
        self.app_controller.rc_controller.set_send_interval_ms(value)
        self.flight_action_cluster.set_rc_interval_value(self.app_controller.rc_controller.send_interval_ms)

    def _on_gesture_toggle_clicked(self) -> None:
        self.app_controller.gesture_controller.toggle()
        self.app_state.gesture_enabled = self.app_controller.gesture_controller.is_enabled()

        if not self.app_state.gesture_enabled:
            self.app_controller.gesture_controller.disable()
            self.gesture_inference_service.reset()
            self.runtime.clear_pending_gesture_frames()

        self._sync_ui_from_state()

    def _on_left_stick_changed(self, x_value: int, y_value: int) -> None:
        if self._is_shutting_down:
            return
        self.app_controller.rc_controller.set_left_stick(x_value, y_value)
        self.runtime.call_api(
            lambda: self.app_controller.rc_controller.flush(),
            on_api_error=self._on_status_error,
            suppress_noop=True,
        )

    def _on_right_stick_changed(self, x_value: int, y_value: int) -> None:
        if self._is_shutting_down:
            return
        self.app_controller.rc_controller.set_right_stick(x_value, y_value)
        self.runtime.call_api(
            lambda: self.app_controller.rc_controller.flush(),
            on_api_error=self._on_status_error,
            suppress_noop=True,
        )

    def _on_stick_released(self) -> None:
        if self._is_shutting_down:
            return
        state = self.app_controller.rc_controller.get_state()
        if state.is_neutral():
            self.runtime.call_api(
                self.app_controller.rc_controller.reset,
                on_api_error=self._on_status_error,
                suppress_noop=True,
            )
            return
        self.runtime.call_api(
            lambda: self.app_controller.rc_controller.flush(force=True),
            on_api_error=self._on_status_error,
            suppress_noop=True,
        )

    def _on_raw_frame_ready(self, frame: object) -> None:
        if self._is_shutting_down:
            return

        if not self.app_controller.gesture_controller.is_enabled():
            return

        self.runtime.enqueue_gesture_frame(frame)

    def _process_pending_gesture_frame(self) -> None:
        if self._is_shutting_down:
            return
        if not self.app_controller.gesture_controller.is_enabled():
            self.runtime.clear_pending_gesture_frames()
            return
        debug_state = self.runtime.process_pending_gesture_frame(on_api_error=self._on_status_error)
        if debug_state is None:
            return
        self._sync_gesture_panel_from_state(debug_state)

    def _on_status_updated(self, status_data: dict, state_data: object, diag_data: dict) -> None:
        if self._is_shutting_down:
            return
        self.runtime.apply_status_update(status_data, state_data, diag_data)
        self._sync_ui_from_state()

    def _on_status_error(self, error_text: str) -> None:
        if self._is_shutting_down:
            return
        self.runtime.apply_status_error(error_text)
        self._sync_ui_from_state()

    def _sync_ui_from_state(self) -> None:
        self._sync_hud_from_app_state()
        self._sync_gesture_panel_from_state()
        self.video_surface.set_stream_status(self.app_state.stream_status)

    def _sync_hud_from_app_state(self) -> None:
        health = self.app_state.health
        drone_text = "Connected" if health.drone_connected else "Offline"
        sdk_text = "Ready" if health.sdk_mode_ready else "Unavailable"
        video_text = self.app_state.stream_status
        detector_text = "Ready" if health.detector_ready else (health.detector_error_reason or "Unavailable")
        command_text = health.last_command_status.upper()
        startup_text = (self.app_state.startup_summary.overall_status if self.app_state.startup_summary else "pending").upper()

        self.hud_top_bar.connection_label.setText(f"Drone: {drone_text}")
        self.hud_top_bar.sdk_label.setText(f"SDK: {sdk_text}")
        self.hud_top_bar.video_label.setText(f"Video: {video_text}")
        self.hud_top_bar.command_label.setText(f"Command: {command_text}")
        self.hud_top_bar.startup_label.setText(f"Startup: {startup_text}")
        self.hud_top_bar.detector_label.setText(f"Detector: {self._compact_health_text(detector_text)}")
        self.hud_top_bar.mode_label.setText(f"Mode: {health.current_mode}")
        self.hud_top_bar.battery_label.setText(
            f"Battery: {self.app_state.battery_pct}%"
            if self.app_state.battery_pct is not None
            else "Battery: --"
        )
        self.hud_top_bar.altitude_label.setText(
            f"Height: {self.app_state.height_cm} cm"
            if self.app_state.height_cm is not None
            else "Height: --"
        )

    def _sync_gesture_panel_from_state(
        self,
        debug_state: dict[str, str | float | bool | None] | None = None,
    ) -> None:
        state = debug_state or self.app_controller.gesture_controller.get_debug_state()
        button = self.gesture_debug_panel.gesture_toggle_button

        if self.app_state.gesture_enabled:
            button.setText("GESTURE ON")
            button.setProperty("state", "on")
        else:
            button.setText("GESTURE OFF")
            button.setProperty("state", "off")

        detector_available_state = state.get("detector_available")
        detector_status_state = state.get("detector_status")
        if self.app_state.gesture_enabled and isinstance(detector_available_state, bool):
            detector_available = detector_available_state
        else:
            detector_available = self.gesture_inference_service.is_detector_available()
        if self.app_state.gesture_enabled and isinstance(detector_status_state, str):
            detector_status = detector_status_state
        else:
            detector_status = self.gesture_inference_service.get_detector_status()
        detector_error = state.get("detector_error")
        if not isinstance(detector_error, str):
            detector_error = self.gesture_inference_service.get_detector_error()
        if not self._is_shutting_down:
            self.app_state.set_detector_state(
                ready=detector_status == "detector_ready",
                error_reason=None if detector_status == "detector_ready" else detector_error,
            )
        self.gesture_debug_panel.gesture_label.setText(f"Gesture: {state['gesture']}")
        self.gesture_debug_panel.detector_label.setText(
            f"Detector: {self._format_detector_status(detector_status, detector_available)}"
        )
        self.gesture_debug_panel.raw_label.setText(f"Raw: {self._safe_debug_text(state.get('raw'))}")
        self.gesture_debug_panel.stable_label.setText(f"Stable: {self._safe_debug_text(state.get('stable'))}")

        confidence = state.get("confidence")
        self.gesture_debug_panel.confidence_label.setText(
            f"Confidence: {confidence:.2f}" if isinstance(confidence, float) else "Confidence: --"
        )
        self.gesture_debug_panel.last_command_label.setText(
            f"Last Command: {self._safe_debug_text(self.app_state.health.last_command_status)}"
        )
        queue_state = self._safe_queue_text(state.get("queue_state"))
        current_label = self._safe_debug_text(self.gesture_logger.get_current_label())
        session_state = "ACTIVE" if self.gesture_logger.is_session_active() else "INACTIVE"
        participant_id = self.gesture_logger.get_session_context()["participant_id"]
        self.gesture_debug_panel.session_state_label.setText(
            f"Session: {session_state} | Participant: {participant_id} | Label: {current_label}"
        )
        self.gesture_debug_panel.queue_label.setText(f"Queue: {queue_state} | Label: {current_label}")

        button.style().unpolish(button)
        button.style().polish(button)
        button.update()

    def _on_stream_status_changed(self, text: str) -> None:
        if self._is_shutting_down:
            return
        self.runtime.apply_stream_status(text)
        self._sync_ui_from_state()

    @staticmethod
    def _safe_debug_text(value: object) -> str:
        if value is None:
            return "--"
        text = str(value).strip()
        if not text or text.lower() == "none":
            return "--"
        return text

    @staticmethod
    def _safe_queue_text(value: object) -> str:
        text = MainWindow._safe_debug_text(value)
        if text == "--":
            return "idle"
        if text in {"detector_unavailable", "detector_missing_dependency", "detector_init_failed"}:
            return text
        return text

    @staticmethod
    def _format_detector_status(status: str, detector_available: bool) -> str:
        if detector_available or status == "detector_ready":
            return "READY"
        if status == "detector_missing_dependency":
            return "MISSING DEPENDENCY"
        if status == "detector_init_failed":
            return "INIT FAILED"
        return "UNAVAILABLE"

    @staticmethod
    def _compact_health_text(text: str) -> str:
        value = MainWindow._safe_debug_text(text)
        return value[:28]
