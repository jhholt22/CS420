from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from clients.python_ui.app.ui.ui_vars import AppUiVars


class StatusPanel(ttk.LabelFrame):
    def __init__(self, parent: tk.Misc, ui_vars: AppUiVars) -> None:
        super().__init__(parent, text="Server State", padding=14, style="Card.TLabelframe")
        self.ui_vars = ui_vars
        self._build()

    def _build(self) -> None:
        self.columnconfigure(1, weight=1)

        self._add_row(0, "Running:", self.ui_vars.status_var)
        self._add_row(1, "Mode:", self.ui_vars.mode_var)
        self._add_row(2, "Flying:", self.ui_vars.flight_var)
        self._add_row(3, "Battery:", self.ui_vars.battery_var)
        self._add_row(4, "Height:", self.ui_vars.height_var)

    def _add_row(self, row: int, label_text: str, value_var: tk.Variable) -> None:
        label = ttk.Label(self, text=label_text, style="Muted.TLabel")
        label.grid(row=row, column=0, sticky="w", padx=(0, 10), pady=2)

        value = ttk.Label(self, textvariable=value_var, style="Value.TLabel")
        value.grid(row=row, column=1, sticky="w", pady=2)