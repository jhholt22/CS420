from __future__ import annotations

import time
import threading
import tkinter as tk
from tkinter import ttk

import requests

from clients.python_ui.app.gesture.inference import GestureInference
from clients.python_ui.app.gesture.mapper import GestureCommandMapper

API_BASE = "http://127.0.0.1:5000/api"
VIDEO_URL = "http://127.0.0.1:8080/video"


class AeroMindClientApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("AeroMind Python UI")
        self.root.geometry("760x720")

        self.api_base = API_BASE
        self.http = requests.Session()

        self.status_var = tk.StringVar(value="Unknown")
        self.mode_var = tk.StringVar(value="-")
        self.flight_var = tk.StringVar(value="-")
        self.battery_var = tk.StringVar(value="-")
        self.height_var = tk.StringVar(value="-")
        self.video_var = tk.StringVar(value=VIDEO_URL)

        self.gesture_mapper = GestureCommandMapper()
        self.simulated_gesture_var = tk.StringVar(value="NONE")
        self.gesture_enabled = tk.BooleanVar(value=False)
        self.gesture_status_var = tk.StringVar(value="Gesture: OFF")
        self.raw_gesture_var = tk.StringVar(value="Raw: -")
        self.stable_gesture_var = tk.StringVar(value="Stable: -")
        self.last_sent_command_var = tk.StringVar(value="Last Command: -")

        self.gesture_inference = GestureInference(
            simulation_provider=self._get_simulated_gesture,
            stability_ms=800,
        )

        self.command_cooldown_seconds = 1.2
        self._last_command_sent_at = 0.0
        self._last_command_sent_value: str | None = None

        self._status_refresh_in_progress = False

        self._build_ui()
        self._bind_keys()

        self.root.after(100, self._refresh_status_async)
        self.root.after(200, self._gesture_tick)
        self.root.after(1000, self._status_tick)

    def _bind_keys(self) -> None:
        self.root.bind("<Up>", lambda e: self.send_cmd("forward 50"))
        self.root.bind("<Down>", lambda e: self.send_cmd("back 50"))
        self.root.bind("<Left>", lambda e: self.send_cmd("ccw 30"))
        self.root.bind("<Right>", lambda e: self.send_cmd("cw 30"))
        self.root.bind("<space>", lambda e: self.send_cmd("takeoff"))
        self.root.bind("<Escape>", lambda e: self.send_cmd("land"))

    def _build_ui(self) -> None:
        self.main_frame = ttk.Frame(self.root, padding=16)
        self.main_frame.pack(fill="both", expand=True)

        title = ttk.Label(
            self.main_frame,
            text="AeroMind Client",
            font=("Segoe UI", 16, "bold"),
        )
        title.pack(anchor="w", pady=(0, 12))

        self._build_status_panel()
        self._build_action_panel()
        self._build_video_panel()
        self._build_manual_controls_panel()
        self._build_gesture_controls_panel()

    def _build_status_panel(self) -> None:
        status_box = ttk.LabelFrame(self.main_frame, text="Server State", padding=12)
        status_box.pack(fill="x", pady=(0, 12))

        ttk.Label(status_box, text="Running:").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=2)
        ttk.Label(status_box, textvariable=self.status_var).grid(row=0, column=1, sticky="w", pady=2)

        ttk.Label(status_box, text="Mode:").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=2)
        ttk.Label(status_box, textvariable=self.mode_var).grid(row=1, column=1, sticky="w", pady=2)

        ttk.Label(status_box, text="Flying:").grid(row=2, column=0, sticky="w", padx=(0, 10), pady=2)
        ttk.Label(status_box, textvariable=self.flight_var).grid(row=2, column=1, sticky="w", pady=2)

        ttk.Label(status_box, text="Battery:").grid(row=3, column=0, sticky="w", padx=(0, 10), pady=2)
        ttk.Label(status_box, textvariable=self.battery_var).grid(row=3, column=1, sticky="w", pady=2)

        ttk.Label(status_box, text="Height:").grid(row=4, column=0, sticky="w", padx=(0, 10), pady=2)
        ttk.Label(status_box, textvariable=self.height_var).grid(row=4, column=1, sticky="w", pady=2)

    def _build_action_panel(self) -> None:
        actions = ttk.LabelFrame(self.main_frame, text="Actions", padding=12)
        actions.pack(fill="x", pady=(0, 12))

        ttk.Button(actions, text="Refresh", command=self._refresh_status_async).grid(row=0, column=0, padx=4, pady=4)
        ttk.Button(actions, text="Start SIM", command=lambda: self.start_controller("sim")).grid(row=0, column=1, padx=4, pady=4)
        ttk.Button(actions, text="Start DRONE", command=lambda: self.start_controller("drone")).grid(row=0, column=2, padx=4, pady=4)
        ttk.Button(actions, text="Stop", command=self.stop_controller).grid(row=0, column=3, padx=4, pady=4)

    def _build_video_panel(self) -> None:
        video_box = ttk.LabelFrame(self.main_frame, text="Video Stream", padding=12)
        video_box.pack(fill="x", pady=(0, 12))

        ttk.Label(video_box, text="MJPEG URL:").grid(row=0, column=0, sticky="w", padx=(0, 10))
        ttk.Entry(video_box, textvariable=self.video_var, width=60).grid(row=0, column=1, sticky="we")

        info = ttk.Label(
            video_box,
            text="Stub inference is active now. Real frame-based detection can be plugged in later.",
            justify="left",
        )
        info.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

    def _build_manual_controls_panel(self) -> None:
        controls = ttk.LabelFrame(self.main_frame, text="Manual Controller", padding=12)
        controls.pack(fill="x", pady=(0, 12))

        controls.columnconfigure((0, 1, 2), weight=1)

        ttk.Button(controls, text="⟲ CCW", command=lambda: self.send_cmd("ccw 90")).grid(row=0, column=0, padx=6, pady=6, sticky="ew")
        ttk.Button(controls, text="↑ Forward", command=lambda: self.send_cmd("forward 50")).grid(row=1, column=1, padx=6, pady=6, sticky="ew")
        ttk.Button(controls, text="⟳ CW", command=lambda: self.send_cmd("cw 90")).grid(row=0, column=2, padx=6, pady=6, sticky="ew")
        ttk.Button(controls, text="← Left", command=lambda: self.send_cmd("left 50")).grid(row=2, column=0, padx=6, pady=6, sticky="ew")
        ttk.Button(controls, text="TAKEOFF", command=lambda: self.send_cmd("takeoff")).grid(row=2, column=1, padx=6, pady=6, sticky="ew")
        ttk.Button(controls, text="→ Right", command=lambda: self.send_cmd("right 50")).grid(row=2, column=2, padx=6, pady=6, sticky="ew")
        ttk.Button(controls, text="↓ Back", command=lambda: self.send_cmd("back 50")).grid(row=3, column=1, padx=6, pady=6, sticky="ew")
        ttk.Button(controls, text="LAND", command=lambda: self.send_cmd("land")).grid(row=4, column=1, padx=6, pady=6, sticky="ew")
        ttk.Button(controls, text="EMERGENCY", command=lambda: self.send_cmd("emergency")).grid(row=5, column=0, columnspan=3, padx=6, pady=10, sticky="ew")

    def _build_gesture_controls_panel(self) -> None:
        frame = ttk.LabelFrame(self.main_frame, text="Gesture Control", padding=12)
        frame.pack(fill="x", pady=(0, 12))

        ttk.Checkbutton(
            frame,
            text="Enable Gesture Control",
            variable=self.gesture_enabled,
        ).grid(row=0, column=0, sticky="w", padx=8, pady=6)

        ttk.Label(frame, text="Simulated Gesture:").grid(row=1, column=0, sticky="w", padx=8, pady=4)

        gesture_values = [
            "NONE",
            "PALM",
            "FIST",
            "THUMB_UP",
            "THUMB_DOWN",
            "POINT_LEFT",
            "POINT_RIGHT",
            "FORWARD",
            "BACKWARD",
            "ROTATE_LEFT",
            "ROTATE_RIGHT",
            "STOP",
        ]

        ttk.Combobox(
            frame,
            textvariable=self.simulated_gesture_var,
            values=gesture_values,
            state="readonly",
            width=18,
        ).grid(row=1, column=1, sticky="w", padx=8, pady=4)

        ttk.Label(frame, textvariable=self.gesture_status_var).grid(row=2, column=0, sticky="w", padx=8, pady=4)
        ttk.Label(frame, textvariable=self.raw_gesture_var).grid(row=2, column=1, sticky="w", padx=8, pady=4)
        ttk.Label(frame, textvariable=self.stable_gesture_var).grid(row=3, column=0, sticky="w", padx=8, pady=4)
        ttk.Label(frame, textvariable=self.last_sent_command_var).grid(row=3, column=1, sticky="w", padx=8, pady=4)

    def start_controller(self, mode: str) -> None:
        threading.Thread(target=self._start_controller_worker, args=(mode,), daemon=True).start()

    def _start_controller_worker(self, mode: str) -> None:
        try:
            response = self.http.post(
                f"{self.api_base}/start",
                json={"mode": mode},
                timeout=3,
            )
            response.raise_for_status()
        except requests.RequestException:
            pass

        self.root.after(0, self._refresh_status_async)

    def stop_controller(self) -> None:
        threading.Thread(target=self._stop_controller_worker, daemon=True).start()

    def _stop_controller_worker(self) -> None:
        try:
            response = self.http.post(
                f"{self.api_base}/stop",
                timeout=3,
            )
            response.raise_for_status()
        except requests.RequestException:
            pass

        self.root.after(0, self._refresh_status_async)

    def send_cmd(self, cmd: str) -> None:
        self._send_api_command(cmd)

    def _refresh_status_async(self) -> None:
        if self._status_refresh_in_progress:
            return

        self._status_refresh_in_progress = True
        threading.Thread(target=self._safe_refresh_status, daemon=True).start()

    def _safe_refresh_status(self) -> None:
        try:
            status_res = self.http.get(f"{self.api_base}/status", timeout=2)
            status_res.raise_for_status()
            status_data = status_res.json()

            if status_data.get("running"):
                state_res = self.http.get(f"{self.api_base}/state", timeout=2)
                state_res.raise_for_status()
                state_data = state_res.json()
            else:
                state_data = None

            self.root.after(0, self._update_status_ui, status_data, state_data)

        except requests.RequestException:
            self.root.after(0, self._set_status_unavailable)
        finally:
            self._status_refresh_in_progress = False

    def _update_status_ui(self, status_data: dict, state_data: dict | None) -> None:
        self.status_var.set(str(status_data.get("running", False)))
        self.mode_var.set(str(status_data.get("mode", "-")))

        if state_data is None:
            self.flight_var.set("-")
            self.battery_var.set("-")
            self.height_var.set("-")
            return

        self.flight_var.set(str(state_data.get("is_flying", "-")))
        battery = state_data.get("battery_pct")
        self.battery_var.set(str(battery) if battery is not None else "-")
        self.height_var.set(str(state_data.get("height_cm", "-")))

    def _set_status_unavailable(self) -> None:
        self.status_var.set("Unavailable")
        self.mode_var.set("-")
        self.flight_var.set("-")
        self.battery_var.set("-")
        self.height_var.set("-")

    def _status_tick(self) -> None:
        self._refresh_status_async()
        self.root.after(1000, self._status_tick)

    def _get_simulated_gesture(self) -> str | None:
        value = self.simulated_gesture_var.get().strip().upper()
        return value or None

    def _gesture_tick(self) -> None:
        try:
            if not self.gesture_enabled.get():
                self.gesture_status_var.set("Gesture: OFF")
                self.raw_gesture_var.set("Raw: -")
                self.stable_gesture_var.set("Stable: -")
                return

            prediction = self.gesture_inference.process(frame=None)

            self.gesture_status_var.set("Gesture: ON")
            self.raw_gesture_var.set(f"Raw: {prediction.raw_gesture or '-'}")
            self.stable_gesture_var.set(
                f"Stable: {prediction.stable_gesture or '-'} ({prediction.stable_for_ms} ms)"
            )

            if prediction.stable_gesture:
                self._dispatch_gesture_command(prediction.stable_gesture)

        except Exception as exc:
            self.gesture_status_var.set(f"Gesture Error: {exc}")
        finally:
            self.root.after(200, self._gesture_tick)

    def _dispatch_gesture_command(self, stable_gesture: str) -> None:
        spec = self.gesture_mapper.map_gesture(stable_gesture)
        if spec is None:
            return

        now = time.monotonic()

        if (now - self._last_command_sent_at) < self.command_cooldown_seconds:
            return

        ok = self._send_api_command(spec.command)
        if not ok:
            return

        self._last_command_sent_at = now
        self._last_command_sent_value = spec.command
        self.last_sent_command_var.set(f"Last Command: {spec.command}")

    def _send_api_command(self, command: str) -> bool:
        def worker() -> None:
            try:
                self.http.post(
                    f"{self.api_base}/command",
                    json={"command": command},
                    timeout=2,
                )
            except requests.RequestException:
                pass

        threading.Thread(target=worker, daemon=True).start()
        return True