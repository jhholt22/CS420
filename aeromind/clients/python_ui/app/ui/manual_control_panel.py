from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from clients.python_ui.app.ui.ui_vars import AppUiVars
from clients.python_ui.app.ui.virtual_stick import VirtualStick


class ManualControlPanel(ttk.LabelFrame):
    def __init__(
        self,
        parent: tk.Misc,
        ui_vars: AppUiVars,
        on_left_stick_change: Callable[[int, int], None],
        on_right_stick_change: Callable[[int, int], None],
        on_takeoff: Callable[[], None],
        on_land: Callable[[], None],
        on_emergency: Callable[[], None],
    ) -> None:
        super().__init__(parent, text="Manual Controller", padding=14, style="Card.TLabelframe")

        self.ui_vars = ui_vars
        self.on_left_stick_change = on_left_stick_change
        self.on_right_stick_change = on_right_stick_change
        self.on_takeoff = on_takeoff
        self.on_land = on_land
        self.on_emergency = on_emergency

        self.left_stick: VirtualStick | None = None
        self.right_stick: VirtualStick | None = None

        self._build()

    def _build(self) -> None:
        sticks_frame = ttk.Frame(self)
        sticks_frame.pack(fill="x")

        self.left_stick = VirtualStick(
            sticks_frame,
            "Left Stick (Yaw / Up-Down)",
            self.on_left_stick_change,
        )
        self.left_stick.pack(side="left", padx=12)

        self.right_stick = VirtualStick(
            sticks_frame,
            "Right Stick (Left-Right / Forward-Back)",
            self.on_right_stick_change,
        )
        self.right_stick.pack(side="left", padx=12)

        buttons_frame = ttk.Frame(self)
        buttons_frame.pack(fill="x", pady=(12, 0))
        buttons_frame.columnconfigure((0, 1, 2), weight=1)

        ttk.Button(
            buttons_frame,
            text="TAKEOFF",
            command=self.on_takeoff,
            style="App.TButton",
        ).grid(row=0, column=0, padx=6, pady=6, sticky="ew")

        ttk.Button(
            buttons_frame,
            text="LAND",
            command=self.on_land,
            style="Secondary.TButton",
        ).grid(row=0, column=1, padx=6, pady=6, sticky="ew")

        ttk.Button(
            buttons_frame,
            text="EMERGENCY",
            command=self.on_emergency,
            style="Danger.TButton",
        ).grid(row=0, column=2, padx=6, pady=6, sticky="ew")
        ttk.Label(self, textvariable=self.ui_vars.left_stick_var, style="Muted.TLabel").pack(anchor="w", pady=(12, 2))
        ttk.Label(self, textvariable=self.ui_vars.right_stick_var, style="Muted.TLabel").pack(anchor="w", pady=2)
        ttk.Label(self, textvariable=self.ui_vars.rc_status_var, style="Value.TLabel").pack(anchor="w", pady=(2, 0))