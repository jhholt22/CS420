from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from clients.python_ui.app.ui.ui_vars import AppUiVars


class VideoPanel(ttk.LabelFrame):
    def __init__(self, parent: tk.Misc, ui_vars: AppUiVars) -> None:
        super().__init__(parent, text="Video Stream", padding=14, style="Card.TLabelframe")
        self.ui_vars = ui_vars
        self.preview_label: tk.Label | None = None

        self._build()

    def _build(self) -> None:
        self.columnconfigure(1, weight=1)

        ttk.Label(self, text="MJPEG URL:", style="Muted.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 10)
        )

        ttk.Entry(self, textvariable=self.ui_vars.video_var, width=60, style="App.TEntry").grid(
            row=0, column=1, sticky="we"
        )

        info_label = ttk.Label(
            self,
            text="MJPEG frames are read in the background and fed into MediaPipe gesture detection.",
            justify="left",
            style="Muted.TLabel",
        )
        info_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

        self.preview_label = tk.Label(
            self,
            text="Waiting for video...",
            bg="#0b1220",
            fg="#e5e7eb",
            bd=1,
            relief="solid",
            width=60,
            height=18,
        )
        self.preview_label.grid(row=2, column=0, columnspan=2, sticky="we", pady=(10, 0))

    def set_waiting(self) -> None:
        if self.preview_label is not None:
            self.preview_label.configure(image="", text="Waiting for video...")

    def set_unavailable(self) -> None:
        if self.preview_label is not None:
            self.preview_label.configure(image="", text="Preview unavailable")

    def set_preview_image(self, photo) -> None:
        if self.preview_label is not None:
            self.preview_label.configure(image=photo, text="")
            self.preview_label.image = photo