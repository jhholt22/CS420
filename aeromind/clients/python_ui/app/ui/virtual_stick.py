from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable


class VirtualStick:
    def __init__(
        self,
        parent: tk.Misc,
        title: str,
        on_change: Callable[[int, int], None],
        size: int = 140,
        knob_radius: int = 14,
    ) -> None:
        self.size = size
        self.knob_radius = knob_radius
        self.max_offset = (size / 2) - knob_radius - 6
        self._on_change = on_change
        self._x = 0.0
        self._y = 0.0

        self.frame = ttk.Frame(parent, style="Panel.TFrame")

        self.title_label = ttk.Label(
            self.frame,
            text=title,
            style="Muted.TLabel",
        )
        self.title_label.pack(anchor="center", pady=(0, 6))

        self.canvas = tk.Canvas(
            self.frame,
            width=size,
            height=size,
            bg="#0b1220",
            highlightthickness=1,
            highlightbackground="#334155",
        )
        self.canvas.pack()

        center = size / 2
        self.canvas.create_oval(8, 8, size - 8, size - 8, outline="#475569", width=2)
        self.canvas.create_line(center, 8, center, size - 8, fill="#334155")
        self.canvas.create_line(8, center, size - 8, center, fill="#334155")

        self._knob = self.canvas.create_oval(0, 0, 0, 0, fill="#22c55e", outline="")
        self._draw_knob()

        self.canvas.bind("<Button-1>", self._on_drag)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

    def pack(self, **kwargs) -> None:
        self.frame.pack(**kwargs)

    def grid(self, **kwargs) -> None:
        self.frame.grid(**kwargs)

    def _on_drag(self, event: tk.Event) -> None:
        center = self.size / 2
        raw_x = max(-self.max_offset, min(self.max_offset, event.x - center))
        raw_y = max(-self.max_offset, min(self.max_offset, event.y - center))

        self._x = raw_x
        self._y = raw_y

        self._draw_knob()
        self._emit_change()

    def _on_release(self, _event: tk.Event) -> None:
        self._x = 0.0
        self._y = 0.0

        self._draw_knob()
        self._emit_change()

    def _draw_knob(self) -> None:
        center = self.size / 2
        x = center + self._x
        y = center + self._y
        r = self.knob_radius

        self.canvas.coords(self._knob, x - r, y - r, x + r, y + r)

    def _emit_change(self) -> None:
        self._on_change(self._normalized_x(), self._normalized_y())

    def _normalized_x(self) -> int:
        return int(round((self._x / self.max_offset) * 100))

    def _normalized_y(self) -> int:
        return int(round((-self._y / self.max_offset) * 100))