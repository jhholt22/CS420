from __future__ import annotations

import tkinter as tk

from clients.python_ui.app.ui.app import AeroMindClientApp


def main() -> None:
    root = tk.Tk()
    AeroMindClientApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()