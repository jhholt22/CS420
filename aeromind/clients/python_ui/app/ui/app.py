from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import requests


API_BASE = "http://127.0.0.1:5000/api"
VIDEO_URL = "http://127.0.0.1:8080/video"


class AeroMindClientApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("AeroMind Python UI")
        self.root.geometry("720x520")

        self.status_var = tk.StringVar(value="Unknown")
        self.mode_var = tk.StringVar(value="-")
        self.flight_var = tk.StringVar(value="-")
        self.battery_var = tk.StringVar(value="-")
        self.height_var = tk.StringVar(value="-")
        self.video_var = tk.StringVar(value=VIDEO_URL)
        self.root.bind("<Up>", lambda e: self.send_cmd("forward 50"))
        self.root.bind("<Down>", lambda e: self.send_cmd("back 50"))
        self.root.bind("<Left>", lambda e: self.send_cmd("ccw 30"))
        self.root.bind("<Right>", lambda e: self.send_cmd("cw 30"))
        self.root.bind("<space>", lambda e: self.send_cmd("takeoff"))
        self.root.bind("<Escape>", lambda e: self.send_cmd("land"))
        self._build_ui()
        self.refresh_status()

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=16)
        frame.pack(fill="both", expand=True)

        title = ttk.Label(frame, text="AeroMind Client", font=("Segoe UI", 16, "bold"))
        title.pack(anchor="w", pady=(0, 12))

        status_box = ttk.LabelFrame(frame, text="Server State", padding=12)
        status_box.pack(fill="x", pady=(0, 12))

        ttk.Label(status_box, text="Running:").grid(row=0, column=0, sticky="w", padx=(0, 10))
        ttk.Label(status_box, textvariable=self.status_var).grid(row=0, column=1, sticky="w")

        ttk.Label(status_box, text="Mode:").grid(row=1, column=0, sticky="w", padx=(0, 10))
        ttk.Label(status_box, textvariable=self.mode_var).grid(row=1, column=1, sticky="w")

        ttk.Label(status_box, text="Flying:").grid(row=2, column=0, sticky="w", padx=(0, 10))
        ttk.Label(status_box, textvariable=self.flight_var).grid(row=2, column=1, sticky="w")

        ttk.Label(status_box, text="Battery:").grid(row=3, column=0, sticky="w", padx=(0, 10))
        ttk.Label(status_box, textvariable=self.battery_var).grid(row=3, column=1, sticky="w")

        ttk.Label(status_box, text="Height:").grid(row=4, column=0, sticky="w", padx=(0, 10))
        ttk.Label(status_box, textvariable=self.height_var).grid(row=4, column=1, sticky="w")

        controls = ttk.LabelFrame(frame, text="Actions", padding=12)
        controls.pack(fill="x", pady=(0, 12))

        ttk.Button(controls, text="Refresh", command=self.refresh_status).grid(row=0, column=0, padx=4, pady=4)
        ttk.Button(controls, text="Start SIM", command=lambda: self.start_controller("sim")).grid(row=0, column=1, padx=4, pady=4)
        ttk.Button(controls, text="Start DRONE", command=lambda: self.start_controller("drone")).grid(row=0, column=2, padx=4, pady=4)
        ttk.Button(controls, text="Stop", command=self.stop_controller).grid(row=0, column=3, padx=4, pady=4)

        video_box = ttk.LabelFrame(frame, text="Video Stream", padding=12)
        video_box.pack(fill="x", pady=(0, 12))

        ttk.Label(video_box, text="MJPEG URL:").grid(row=0, column=0, sticky="w", padx=(0, 10))
        ttk.Entry(video_box, textvariable=self.video_var, width=60).grid(row=0, column=1, sticky="we")

        info = ttk.Label(
            frame,
            text="This UI currently reads the API and stream URL only.\nGesture inference can be added later on the client side.",
            justify="left",
        )
        info.pack(anchor="w")
        controls = ttk.LabelFrame(frame, text="Controller", padding=12)
        controls.pack(fill="x", pady=(0, 12))

        # --- GRID LAYOUT ---
        controls.columnconfigure((0, 1, 2), weight=1)

        # ROW 0 (rotation)
        ttk.Button(controls, text="⟲ CCW", command=lambda: self.send_cmd("ccw 90")).grid(row=0, column=0, padx=6, pady=6, sticky="ew")
        ttk.Button(controls, text="⟳ CW", command=lambda: self.send_cmd("cw 90")).grid(row=0, column=2, padx=6, pady=6, sticky="ew")

        # ROW 1 (movement)
        ttk.Button(controls, text="↑ Forward", command=lambda: self.send_cmd("forward 50")).grid(row=1, column=1, padx=6, pady=6, sticky="ew")

        # ROW 2 (center + left/right if you add later)
        ttk.Button(controls, text="TAKEOFF", command=lambda: self.send_cmd("takeoff")).grid(row=2, column=1, padx=6, pady=6, sticky="ew")

        # ROW 3
        ttk.Button(controls, text="↓ Back", command=lambda: self.send_cmd("back 50")).grid(row=3, column=1, padx=6, pady=6, sticky="ew")

        # ROW 4
        ttk.Button(controls, text="LAND", command=lambda: self.send_cmd("land")).grid(row=4, column=1, padx=6, pady=6, sticky="ew")

        # ROW 5 (emergency)
        ttk.Button(
            controls,
            text="EMERGENCY",
            command=lambda: self.send_cmd("emergency")
        ).grid(row=5, column=0, columnspan=3, padx=6, pady=10, sticky="ew")
    def start_controller(self, mode: str) -> None:
        try:
            requests.post(f"{API_BASE}/start", json={"mode": mode}, timeout=3)
        except Exception:
            pass
        self.refresh_status()

    def stop_controller(self) -> None:
        try:
            requests.post(f"{API_BASE}/stop", timeout=3)
        except Exception:
            pass
        self.refresh_status()
    def send_cmd(self, cmd: str):
        try:
            requests.post(f"{API_BASE}/command", json={"command": cmd}, timeout=2)
        except Exception:
            pass
    def refresh_status(self) -> None:
        try:
            status_res = requests.get(f"{API_BASE}/status", timeout=2)
            status_data = status_res.json()

            self.status_var.set(str(status_data.get("running", False)))
            self.mode_var.set(str(status_data.get("mode", "-")))

            if status_data.get("running"):
                state_res = requests.get(f"{API_BASE}/state", timeout=2)
                state_data = state_res.json()

                self.flight_var.set(str(state_data.get("is_flying", "-")))
                val = state_data.get("battery_pct")
                self.battery_var.set(str(val) if val is not None else "-")
                self.height_var.set(str(state_data.get("height_cm", "-")))
            else:
                self.flight_var.set("-")
                self.battery_var.set("-")
                self.height_var.set("-")

        except Exception:
            self.status_var.set("Unavailable")
            self.mode_var.set("-")
            self.flight_var.set("-")
            self.battery_var.set("-")
            self.height_var.set("-")