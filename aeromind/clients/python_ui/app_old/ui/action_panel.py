from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable


class ActionPanel(ttk.LabelFrame):
    def __init__(
        self,
        parent: tk.Misc,
        on_refresh: Callable[[], None],
        on_start_sim: Callable[[], None],
        on_start_drone: Callable[[], None],
        on_stop: Callable[[], None],
    ) -> None:
        super().__init__(parent, text="Actions", padding=14, style="Card.TLabelframe")
        self.on_refresh = on_refresh
        self.on_start_sim = on_start_sim
        self.on_start_drone = on_start_drone
        self.on_stop = on_stop

        self._build()

    def _build(self) -> None:
        ttk.Button(self, text="Refresh", command=self.on_refresh, style="Secondary.TButton").grid(
            row=0, column=0, padx=6, pady=6, sticky="ew"
        )
        ttk.Button(self, text="Start SIM", command=self.on_start_sim, style="App.TButton").grid(
            row=0, column=1, padx=6, pady=6, sticky="ew"
        )
        ttk.Button(self, text="Start DRONE", command=self.on_start_drone, style="App.TButton").grid(
            row=0, column=2, padx=6, pady=6, sticky="ew"
        )
        ttk.Button(self, text="Stop", command=self.on_stop, style="Danger.TButton").grid(
            row=0, column=3, padx=6, pady=6, sticky="ew"
        )

        for col in range(4):
            self.columnconfigure(col, weight=1)