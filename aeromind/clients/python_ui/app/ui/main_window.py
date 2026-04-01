from __future__ import annotations

from PySide6.QtCore import QThread
from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

from app.config import AppConfig
from app.services.api_client import ApiClient, ApiClientError
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
        self.gesture_enabled = False

        self.hud_top_bar.raise_()
        self.left_stick.raise_()
        self.right_stick.raise_()
        self.flight_action_cluster.raise_()
        self.gesture_debug_panel.raise_()

        self.setCentralWidget(central_widget)

        self.config = AppConfig()
        self.api_client = ApiClient(self.config.api_base_url)
        self.video_service = VideoStreamService(self.config.video_url)

        self.status_thread = QThread(self)
        self.status_worker = StatusWorker(self.api_client, self.config.status_refresh_ms)
        self.status_worker.moveToThread(self.status_thread)
        self.status_thread.started.connect(self.status_worker.start)
        self.status_worker.statusUpdated.connect(self._on_status_updated)
        self.status_worker.statusError.connect(self._on_status_error)

        self.video_thread = QThread(self)
        self.video_worker = VideoWorker(
            self.video_service,
            self.config.video_url,
            self.config.video_reconnect_delay_ms,
        )
        self.video_worker.moveToThread(self.video_thread)
        self.video_thread.started.connect(self.video_worker.start)
        self.video_worker.frameReady.connect(self.video_surface.set_video_pixmap)
        self.video_worker.streamStatusChanged.connect(self.video_surface.set_stream_status)

        self._apply_hud_defaults()
        self._apply_debug_defaults()
        self._wire_interactions()
        self._layout_overlays()

        self.status_thread.start()
        self.video_thread.start()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "hud_top_bar"):
            self._layout_overlays()

    def closeEvent(self, event) -> None:
        self.status_worker.stop()
        self.status_thread.quit()
        self.status_thread.wait(1500)

        self.video_worker.stop()
        self.video_thread.quit()
        self.video_thread.wait(2000)
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
        self.hud_top_bar.connection_label.setText("Connection: Disconnected")
        self.hud_top_bar.battery_label.setText("Battery: 85%")
        self.hud_top_bar.mode_label.setText("Mode: --")
        self.hud_top_bar.altitude_label.setText("Height: 0 cm")

    def _apply_debug_defaults(self) -> None:
        self.gesture_debug_panel.gesture_label.setText("Gesture: OFF")
        self.gesture_debug_panel.gesture_toggle_button.setText("GESTURE OFF")
        self.gesture_debug_panel.gesture_toggle_button.setProperty("state", "off")
        self.gesture_debug_panel.gesture_toggle_button.style().unpolish(self.gesture_debug_panel.gesture_toggle_button)
        self.gesture_debug_panel.gesture_toggle_button.style().polish(self.gesture_debug_panel.gesture_toggle_button)
        self.gesture_debug_panel.raw_label.setText("Raw: -")
        self.gesture_debug_panel.stable_label.setText("Stable: -")
        self.gesture_debug_panel.last_command_label.setText("Last Command: -")
        self.gesture_debug_panel.queue_label.setText("Queue: idle")

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

    def _on_start_sim_clicked(self) -> None:
        print("START SIM clicked", flush=True)
        self._call_api(lambda: self.api_client.start_controller("sim"))

    def _on_start_drone_clicked(self) -> None:
        print("START DRONE clicked", flush=True)
        self._call_api(lambda: self.api_client.start_controller("drone"))

    def _on_stop_clicked(self) -> None:
        print("STOP clicked", flush=True)
        self._call_api(self.api_client.stop_controller)

    def _on_takeoff_clicked(self) -> None:
        print("TAKEOFF clicked", flush=True)
        self._call_api(lambda: self.api_client.send_command("takeoff"))

    def _on_land_clicked(self) -> None:
        print("LAND clicked", flush=True)
        self._call_api(lambda: self.api_client.send_command("land"))

    def _on_emergency_clicked(self) -> None:
        print("EMERGENCY clicked", flush=True)
        self._call_api(lambda: self.api_client.send_command("emergency"))

    def _on_gesture_toggle_clicked(self) -> None:
        self.gesture_enabled = not self.gesture_enabled
        button = self.gesture_debug_panel.gesture_toggle_button

        if self.gesture_enabled:
            self.gesture_debug_panel.gesture_label.setText("Gesture: ON")
            button.setText("GESTURE ON")
            button.setProperty("state", "on")
        else:
            self.gesture_debug_panel.gesture_label.setText("Gesture: OFF")
            self.gesture_debug_panel.raw_label.setText("Raw: -")
            self.gesture_debug_panel.stable_label.setText("Stable: -")
            self.gesture_debug_panel.last_command_label.setText("Last Command: -")
            self.gesture_debug_panel.queue_label.setText("Queue: idle")
            button.setText("GESTURE OFF")
            button.setProperty("state", "off")

        button.style().unpolish(button)
        button.style().polish(button)
        button.update()

    def _on_left_stick_changed(self, x_value: int, y_value: int) -> None:
        print(f"LEFT STICK x={x_value} y={y_value}", flush=True)

    def _on_right_stick_changed(self, x_value: int, y_value: int) -> None:
        print(f"RIGHT STICK x={x_value} y={y_value}", flush=True)

    def _on_status_updated(self, status_data: dict, state_data: object) -> None:
        self.hud_top_bar.connection_label.setText("Connection: Connected")
        mode = str(status_data.get("mode", "--"))
        self.hud_top_bar.mode_label.setText(f"Mode: {mode}")

        if isinstance(state_data, dict):
            battery = state_data.get("battery_pct")
            height = state_data.get("height_cm")
            self.hud_top_bar.battery_label.setText(f"Battery: {battery}%" if battery is not None else "Battery: --")
            self.hud_top_bar.altitude_label.setText(f"Height: {height} cm" if height is not None else "Height: --")
            return

        self.hud_top_bar.battery_label.setText("Battery: --")
        self.hud_top_bar.altitude_label.setText("Height: 0 cm")

    def _on_status_error(self, error_text: str) -> None:
        print(error_text, flush=True)
        self.hud_top_bar.connection_label.setText("Connection: Offline")
        self.hud_top_bar.mode_label.setText("Mode: --")

    def _call_api(self, action) -> None:
        try:
            action()
        except ApiClientError as exc:
            self._on_status_error(str(exc))
