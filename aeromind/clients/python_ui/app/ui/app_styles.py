from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class AppTheme:
    BACKGROUND = "#0f172a"
    PANEL_BACKGROUND = "#111827"
    PANEL_BORDER = "#374151"
    TEXT_PRIMARY = "#e5e7eb"
    TEXT_MUTED = "#9ca3af"
    ACCENT = "#2563eb"
    ACCENT_HOVER = "#1d4ed8"
    SUCCESS = "#16a34a"
    WARNING = "#d97706"
    DANGER = "#dc2626"
    INPUT_BACKGROUND = "#0b1220"

    FONT_FAMILY = "Segoe UI"
    FONT_SIZE_NORMAL = 10
    FONT_SIZE_TITLE = 18
    FONT_SIZE_SECTION = 10


def configure_app_styles(root: tk.Tk) -> ttk.Style:
    style = ttk.Style(root)
    style.theme_use("clam")

    root.configure(bg=AppTheme.BACKGROUND)

    # Base defaults
    style.configure(
        ".",
        background=AppTheme.BACKGROUND,
        foreground=AppTheme.TEXT_PRIMARY,
        font=(AppTheme.FONT_FAMILY, AppTheme.FONT_SIZE_NORMAL),
    )

    # Main frame / standard frame
    style.configure(
        "App.TFrame",
        background=AppTheme.BACKGROUND,
    )

    style.configure(
        "Panel.TFrame",
        background=AppTheme.PANEL_BACKGROUND,
    )

    # Title
    style.configure(
        "Title.TLabel",
        background=AppTheme.BACKGROUND,
        foreground="#ffffff",
        font=(AppTheme.FONT_FAMILY, AppTheme.FONT_SIZE_TITLE, "bold"),
    )

    # Standard labels
    style.configure(
        "TLabel",
        background=AppTheme.PANEL_BACKGROUND,
        foreground=AppTheme.TEXT_PRIMARY,
        font=(AppTheme.FONT_FAMILY, AppTheme.FONT_SIZE_NORMAL),
    )

    style.configure(
        "Muted.TLabel",
        background=AppTheme.PANEL_BACKGROUND,
        foreground=AppTheme.TEXT_MUTED,
        font=(AppTheme.FONT_FAMILY, AppTheme.FONT_SIZE_NORMAL),
    )

    style.configure(
        "Value.TLabel",
        background=AppTheme.PANEL_BACKGROUND,
        foreground="#ffffff",
        font=(AppTheme.FONT_FAMILY, AppTheme.FONT_SIZE_NORMAL, "bold"),
    )

    # LabelFrame
    style.configure(
        "Card.TLabelframe",
        background=AppTheme.PANEL_BACKGROUND,
        foreground=AppTheme.TEXT_PRIMARY,
        borderwidth=1,
        relief="solid",
        padding=14,
    )

    style.configure(
        "Card.TLabelframe.Label",
        background=AppTheme.PANEL_BACKGROUND,
        foreground="#ffffff",
        font=(AppTheme.FONT_FAMILY, AppTheme.FONT_SIZE_SECTION, "bold"),
    )

    # Buttons
    style.configure(
        "App.TButton",
        background=AppTheme.ACCENT,
        foreground="#ffffff",
        borderwidth=0,
        focusthickness=0,
        focuscolor=AppTheme.ACCENT,
        padding=(14, 10),
        font=(AppTheme.FONT_FAMILY, 10, "bold"),
    )
    style.map(
        "App.TButton",
        background=[
            ("active", AppTheme.ACCENT_HOVER),
            ("pressed", AppTheme.ACCENT_HOVER),
            ("disabled", "#334155"),
        ],
        foreground=[
            ("disabled", "#94a3b8"),
        ],
    )

    style.configure(
        "Danger.TButton",
        background=AppTheme.DANGER,
        foreground="#ffffff",
        borderwidth=0,
        padding=(14, 10),
        font=(AppTheme.FONT_FAMILY, 10, "bold"),
    )
    style.map(
        "Danger.TButton",
        background=[
            ("active", "#b91c1c"),
            ("pressed", "#b91c1c"),
        ]
    )

    style.configure(
        "Secondary.TButton",
        background="#1f2937",
        foreground="#ffffff",
        borderwidth=0,
        padding=(14, 10),
        font=(AppTheme.FONT_FAMILY, 10, "bold"),
    )
    style.map(
        "Secondary.TButton",
        background=[
            ("active", "#374151"),
            ("pressed", "#374151"),
        ]
    )

    # Entry
    style.configure(
        "App.TEntry",
        fieldbackground=AppTheme.INPUT_BACKGROUND,
        foreground="#ffffff",
        bordercolor=AppTheme.PANEL_BORDER,
        lightcolor=AppTheme.PANEL_BORDER,
        darkcolor=AppTheme.PANEL_BORDER,
        insertcolor="#ffffff",
        padding=8,
    )
    style.map(
        "App.TEntry",
        bordercolor=[("focus", AppTheme.ACCENT)],
        lightcolor=[("focus", AppTheme.ACCENT)],
        darkcolor=[("focus", AppTheme.ACCENT)],
    )

    # Checkbutton
    style.configure(
        "App.TCheckbutton",
        background=AppTheme.PANEL_BACKGROUND,
        foreground=AppTheme.TEXT_PRIMARY,
        font=(AppTheme.FONT_FAMILY, AppTheme.FONT_SIZE_NORMAL),
    )
    style.map(
        "App.TCheckbutton",
        background=[("active", AppTheme.PANEL_BACKGROUND)],
        foreground=[("active", "#ffffff")],
    )

    return style