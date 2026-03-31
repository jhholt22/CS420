from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from clients.python_ui.app.ui.ui_vars import AppUiVars


class GesturePanel(ttk.LabelFrame):
    def __init__(self, parent: tk.Misc, ui_vars: AppUiVars) -> None:
        super().__init__(parent, text="Gesture Control", padding=14, style="Card.TLabelframe")
        self.ui_vars = ui_vars
        self._build()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        ttk.Checkbutton(
            self,
            text="Enable Gesture Control",
            variable=self.ui_vars.gesture_enabled,
            style="App.TCheckbutton",
        ).grid(row=0, column=0, sticky="w", padx=8, pady=6)

        ttk.Label(
            self,
            textvariable=self.ui_vars.gesture_status_var,
            style="Value.TLabel",
        ).grid(row=1, column=0, sticky="w", padx=8, pady=4)

        ttk.Label(
            self,
            textvariable=self.ui_vars.raw_gesture_var,
            style="Muted.TLabel",
        ).grid(row=1, column=1, sticky="w", padx=8, pady=4)

        ttk.Label(
            self,
            textvariable=self.ui_vars.stable_gesture_var,
            style="Value.TLabel",
        ).grid(row=2, column=0, sticky="w", padx=8, pady=4)

        ttk.Label(
            self,
            textvariable=self.ui_vars.last_queued_command_var,
            style="Muted.TLabel",
        ).grid(row=2, column=1, sticky="w", padx=8, pady=4)

        ttk.Label(
            self,
            textvariable=self.ui_vars.last_dispatched_gesture_var,
            style="Muted.TLabel",
        ).grid(row=3, column=0, sticky="w", padx=8, pady=4)

        ttk.Label(
            self,
            textvariable=self.ui_vars.dispatch_status_var,
            style="Value.TLabel",
        ).grid(row=3, column=1, sticky="w", padx=8, pady=4)

        ttk.Label(
            self,
            textvariable=self.ui_vars.last_sent_command_var,
            style="Muted.TLabel",
        ).grid(row=4, column=0, sticky="w", padx=8, pady=4)

        ttk.Label(
            self,
            textvariable=self.ui_vars.command_pipeline_var,
            style="Value.TLabel",
        ).grid(row=4, column=1, sticky="w", padx=8, pady=4)