from __future__ import annotations

from PySide6.QtCore import QThread
from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

from app.config import AppConfig
from app.controllers.app_controller import AppController
from app.models.app_state import AppState
from app.services.api_client import ApiClientError
from app.services.gesture_inference_service import GestureInferenceService
from app.services.telemetry_service import TelemetryService
from app.services.video_stream_service import VideoStreamService
from app.ui.panels.gesture_debug_panel import GestureDebugPanel
from app.ui.panels.hud_top_bar import HudTopBar
from app.ui.panels.video_surface import VideoSurface
from app.ui.widgets.flight_action_cluster import FlightActionCluster
from app.ui.widgets.virtual_stick import VirtualStick
from app.workers.status_worker import StatusWorker
from app.workers.video_worker import VideoWorker


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
        self.telemetry_service = TelemetryService()
        self.video_service = VideoStreamService(
            self.config.video_url,
            prefer_ffmpeg=self.config.video_backend_prefer_ffmpeg,
            max_width=self.config.video_max_width,
            max_height=self.config.video_max_height,
        )

        self.status_thread = QThread(self)
        self.status_worker = StatusWorker(self.app_controller.api_client, self.config.status_refresh_ms)
        self.status_worker.moveToThread(self.status_thread)
        self.status_thread.started.connect(self.status_worker.start)
        self.status_worker.statusUpdated.connect(self._on_status_updated)
        self.status_worker.statusError.connect(self._on_status_error)

        self.video_thread = QThread(self)
        self.video_worker = VideoWorker(
            self.video_service,
            self.config.video_url,
            self.config.video_reconnect_delay_ms,
            read_interval_ms=self.config.video_read_interval_ms,
            drop_frames_on_reconnect=self.config.video_drop_frames_on_reconnect,
        )
        self.video_worker.moveToThread(self.video_thread)
        self.video_thread.started.connect(self.video_worker.start)
        self._connect_worker_signals()

        self._apply_hud_defaults()
        self._apply_debug_defaults()
        self._wire_interactions()
        self._layout_overlays()

        self.status_thread.start()
        self.video_thread.start()

    def _connect_worker_signals(self) -> None:
        self.video_worker.frameReady.connect(self.video_surface.set_video_pixmap)
        self.video_worker.rawFrameReady.connect(self._on_raw_frame_ready)
        self.video_worker.streamStatusChanged.connect(self._on_stream_status_changed)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "hud_top_bar"):
            self._layout_overlays()

    def closeEvent(self, event) -> None:
        if self._is_shutting_down:
            event.accept()
            return

        self._is_shutting_down = True
        self._shutdown_workers()
        self._reset_runtime_state()
        self._sync_ui_from_state()
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
        self.app_state.battery_pct = 85
        self.app_state.height_cm = 0
        self.app_state.set_stream_status("No Signal")
        self._sync_ui_from_state()

    def _apply_debug_defaults(self) -> None:
        self.app_state.gesture_enabled = self.app_controller.gesture_controller.is_enabled()
        self.app_controller.gesture_controller.reset()
        self._sync_ui_from_state()

    def _wire_interactions(self) -> None:
        self.flight_action_cluster.startSimClicked.connect(self._on_start_sim_clicked)
        self.flight_action_cluster.startDroneClicked.connect(self._on_start_drone_clicked)
        self.flight_action_cluster.stopClicked.connect(self._on_stop_clicked)
        self.flight_action_cluster.takeoffClicked.connect(self._on_takeoff_clicked)
        self.flight_action_cluster.landClicked.connect(self._on_land_clicked)
        self.flight_action_cluster.emergencyClicked.connect(self._on_emergency_clicked)
        self.gesture_debug_panel.gestureToggleClicked.connect(self._on_gesture_toggle_clicked)

        self.left_stick.valueChanged.connect(self._on_left_stick_changed)
        self.right_stick.valueChanged.connect(self._on_right_stick_changed)
        self.left_stick.stickReleased.connect(self._on_stick_released)
        self.right_stick.stickReleased.connect(self._on_stick_released)

    def _on_start_sim_clicked(self) -> None:
        self._call_api(self.app_controller.command_controller.start_sim)

    def _on_start_drone_clicked(self) -> None:
        self._call_api(self.app_controller.command_controller.start_drone)

    def _on_stop_clicked(self) -> None:
        self._call_api(self.app_controller.command_controller.stop)

    def _on_takeoff_clicked(self) -> None:
        self._call_api(self.app_controller.command_controller.takeoff)

    def _on_land_clicked(self) -> None:
        self._call_api(self.app_controller.command_controller.land)

    def _on_emergency_clicked(self) -> None:
        self._call_api(self.app_controller.command_controller.emergency)

    def _on_gesture_toggle_clicked(self) -> None:
        self.app_controller.gesture_controller.toggle()
        self.app_state.gesture_enabled = self.app_controller.gesture_controller.is_enabled()

        if not self.app_state.gesture_enabled:
            self.app_controller.gesture_controller.disable()
            self.gesture_inference_service.reset()

        self._sync_ui_from_state()

    def _on_left_stick_changed(self, x_value: int, y_value: int) -> None:
        if self._is_shutting_down:
            return
        self.app_controller.rc_controller.set_left_stick(x_value, y_value)
        self._call_api(lambda: self.app_controller.rc_controller.flush(), suppress_noop=True)

    def _on_right_stick_changed(self, x_value: int, y_value: int) -> None:
        if self._is_shutting_down:
            return
        self.app_controller.rc_controller.set_right_stick(x_value, y_value)
        self._call_api(lambda: self.app_controller.rc_controller.flush(), suppress_noop=True)

    def _on_stick_released(self) -> None:
        if self._is_shutting_down:
            return
        state = self.app_controller.rc_controller.get_state()
        if state.is_neutral():
            self._call_api(self.app_controller.rc_controller.reset, suppress_noop=True)
            return
        self._call_api(lambda: self.app_controller.rc_controller.flush(force=True), suppress_noop=True)

    def _on_raw_frame_ready(self, frame: object) -> None:
        if self._is_shutting_down or not self.app_controller.gesture_controller.is_enabled():
            return

        try:
            result = self.gesture_inference_service.process_frame(frame)
            debug_state = self.app_controller.gesture_controller.update_from_result(result)
            self._sync_gesture_panel_from_state(debug_state)

            command_name = result.command_name
            if self.app_controller.gesture_controller.should_dispatch_command(command_name):
                assert command_name is not None
                self._call_api(lambda: self.app_controller.command_controller.execute_gesture_command(command_name))
                self.app_controller.gesture_controller.mark_command_dispatched(command_name)
                self._sync_gesture_panel_from_state()
        except ApiClientError as exc:
            self._on_status_error(str(exc))
        except Exception:
            self._sync_gesture_panel_from_state()

    def _on_status_updated(self, status_data: dict, state_data: object) -> None:
        if self._is_shutting_down:
            return
        telemetry = self.telemetry_service.build_telemetry(status_data, state_data)
        self.app_state.mark_connected(telemetry.mode)
        self.app_state.update_from_telemetry(telemetry)
        self._sync_ui_from_state()

    def _on_status_error(self, error_text: str) -> None:
        if self._is_shutting_down:
            return
        self.app_state.mark_disconnected(error_text)
        self._sync_ui_from_state()

    def _shutdown_workers(self) -> None:
        self._safe_stop_worker(self.status_worker)
        self._safe_quit_thread(self.status_thread, 1500)
        self._safe_stop_worker(self.video_worker)
        self._safe_quit_thread(self.video_thread, 2000)

    def _reset_runtime_state(self) -> None:
        self.gesture_inference_service.reset()
        self.app_controller.gesture_controller.disable()
        self.app_state.gesture_enabled = False
        self.app_controller.rc_controller.reset()
        self.video_service.close()
        self.app_state.reset_runtime_state()

    def _sync_ui_from_state(self) -> None:
        self._sync_hud_from_app_state()
        self._sync_gesture_panel_from_state()
        self.video_surface.set_stream_status(self.app_state.stream_status)

    def _sync_hud_from_app_state(self) -> None:
        connection_text = "Connected" if self.app_state.connected else "Offline"
        self.hud_top_bar.connection_label.setText(f"Connection: {connection_text}")
        self.hud_top_bar.mode_label.setText(f"Mode: {self.app_state.mode}")
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

        detector_available = bool(state.get("detector_available", self.gesture_inference_service.is_detector_available()))
        self.gesture_debug_panel.gesture_label.setText(f"Gesture: {state['gesture']}")
        self.gesture_debug_panel.detector_label.setText(
            "Detector: READY" if detector_available else "Detector: OFFLINE"
        )
        self.gesture_debug_panel.raw_label.setText(f"Raw: {self._safe_debug_text(state.get('raw'))}")
        self.gesture_debug_panel.stable_label.setText(f"Stable: {self._safe_debug_text(state.get('stable'))}")

        confidence = state.get("confidence")
        self.gesture_debug_panel.confidence_label.setText(
            f"Confidence: {confidence:.2f}" if isinstance(confidence, float) else "Confidence: --"
        )
        self.gesture_debug_panel.last_command_label.setText(
            f"Last Command: {self._safe_debug_text(state.get('last_command'))}"
        )
        queue_state = self._safe_queue_text(state.get("queue_state"))
        self.gesture_debug_panel.queue_label.setText(f"Queue: {queue_state}")

        button.style().unpolish(button)
        button.style().polish(button)
        button.update()

    def _on_stream_status_changed(self, text: str) -> None:
        if self._is_shutting_down:
            return
        self.app_state.set_stream_status(text)
        self._sync_ui_from_state()

    def _safe_stop_worker(self, worker: object | None) -> None:
        if worker is None:
            return
        stop = getattr(worker, "stop", None)
        if callable(stop):
            try:
                stop()
            except RuntimeError:
                pass

    def _safe_quit_thread(self, thread: QThread | None, timeout_ms: int) -> None:
        if thread is None:
            return
        if thread.isRunning():
            thread.quit()
            thread.wait(timeout_ms)

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
        if text == "detector_unavailable":
            return "offline"
        return text

    def _call_api(self, action, suppress_noop: bool = False) -> None:
        try:
            result = action()
            if result is None and suppress_noop:
                return
        except ApiClientError as exc:
            self._on_status_error(str(exc))
