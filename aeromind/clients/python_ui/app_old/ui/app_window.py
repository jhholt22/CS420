from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from clients.python_ui.app.ui.action_panel import ActionPanel
from clients.python_ui.app.ui.gesture_panel import GesturePanel
from clients.python_ui.app.ui.manual_control_panel import ManualControlPanel
from clients.python_ui.app.ui.status_panel import StatusPanel
from clients.python_ui.app.ui.ui_vars import AppUiVars
from clients.python_ui.app.ui.video_panel import VideoPanel


class AppWindow:
    def __init__(
        self,
        root: tk.Tk,
        ui_vars: AppUiVars,
        *,
        on_refresh,
        on_start_sim,
        on_start_drone,
        on_stop,
        on_left_stick_change,
        on_right_stick_change,
        on_takeoff,
        on_land,
        on_emergency,
    ) -> None:
        self.root = root
        self.ui_vars = ui_vars

        self.main_frame: ttk.Frame | None = None
        self.title_label: ttk.Label | None = None

        self.status_panel: StatusPanel | None = None
        self.action_panel: ActionPanel | None = None
        self.video_panel: VideoPanel | None = None
        self.manual_control_panel: ManualControlPanel | None = None
        self.gesture_panel: GesturePanel | None = None

        self._callbacks = {
            "on_refresh": on_refresh,
            "on_start_sim": on_start_sim,
            "on_start_drone": on_start_drone,
            "on_stop": on_stop,
            "on_left_stick_change": on_left_stick_change,
            "on_right_stick_change": on_right_stick_change,
            "on_takeoff": on_takeoff,
            "on_land": on_land,
            "on_emergency": on_emergency,
        }

        self._build()

    def _build(self) -> None:
        self.main_frame = ttk.Frame(self.root, padding=20, style="App.TFrame")
        self.main_frame.pack(fill="both", expand=True)

        self.title_label = ttk.Label(
            self.main_frame,
            text="AeroMind Client",
            style="Title.TLabel",
        )
        self.title_label.pack(anchor="w", pady=(0, 16))

        self.status_panel = StatusPanel(self.main_frame, self.ui_vars)
        self.status_panel.pack(fill="x", pady=(0, 12))

        self.action_panel = ActionPanel(
            self.main_frame,
            on_refresh=self._callbacks["on_refresh"],
            on_start_sim=self._callbacks["on_start_sim"],
            on_start_drone=self._callbacks["on_start_drone"],
            on_stop=self._callbacks["on_stop"],
        )
        self.action_panel.pack(fill="x", pady=(0, 12))

        self.video_panel = VideoPanel(self.main_frame, self.ui_vars)
        self.video_panel.pack(fill="x", pady=(0, 12))

        self.manual_control_panel = ManualControlPanel(
            self.main_frame,
            self.ui_vars,
            on_left_stick_change=self._callbacks["on_left_stick_change"],
            on_right_stick_change=self._callbacks["on_right_stick_change"],
            on_takeoff=self._callbacks["on_takeoff"],
            on_land=self._callbacks["on_land"],
            on_emergency=self._callbacks["on_emergency"],
        )
        self.manual_control_panel.pack(fill="x", pady=(0, 12))

        self.gesture_panel = GesturePanel(self.main_frame, self.ui_vars)
        self.gesture_panel.pack(fill="x", pady=(0, 12))