from __future__ import annotations

import time
import threading
import tkinter as tk
from queue import Empty, Queue
from typing import Any
from tkinter import ttk

import cv2
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
        self.gesture_enabled = tk.BooleanVar(value=False)
        self.gesture_status_var = tk.StringVar(value="Gesture: OFF")
        self.raw_gesture_var = tk.StringVar(value="Raw: -")
        self.stable_gesture_var = tk.StringVar(value="Stable: -")
        self.last_queued_command_var = tk.StringVar(value="Last Queued: -")
        self.last_sent_command_var = tk.StringVar(value="Last Command: -")
        self.last_dispatched_gesture_var = tk.StringVar(value="Last Gesture: -")
        self.dispatch_status_var = tk.StringVar(value="Dispatch: idle")
        self.command_pipeline_var = tk.StringVar(value="Command Queue: idle")

        self.gesture_inference = GestureInference(
            stability_ms=1200,
        )

        self.command_cooldown_seconds = 2.0
        self._last_command_sent_at = 0.0
        self._current_stable_gesture: str | None = None
        self._last_dispatched_gesture: str | None = None
        self._last_blocked_signature: tuple[str | None, str] | None = None
        self._last_logged_raw_gesture: str | None = None

        self._status_refresh_in_progress = False
        self._video_lock = threading.Lock()
        self._latest_frame = None
        self._video_running = True
        self._video_thread = threading.Thread(target=self._video_capture_loop, daemon=True)
        self._command_queue: Queue[tuple[dict[str, Any], str] | None] = Queue()
        self._command_worker_running = True
        self._command_worker_thread = threading.Thread(target=self._command_worker_loop, daemon=True)

        self._build_ui()
        self._bind_keys()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._video_thread.start()
        self._command_worker_thread.start()
        self.root.after(100, self._refresh_status_async)
        self.root.after(400, self._gesture_tick)
        self.root.after(1000, self._status_tick)

    def _bind_keys(self) -> None:
        self.root.bind("<Up>", lambda e: self.send_cmd(self._command_payload("forward", distance_cm=50)))
        self.root.bind("<Down>", lambda e: self.send_cmd(self._command_payload("back", distance_cm=50)))
        self.root.bind("<Left>", lambda e: self.send_cmd(self._command_payload("ccw", degrees=30)))
        self.root.bind("<Right>", lambda e: self.send_cmd(self._command_payload("cw", degrees=30)))
        self.root.bind("<space>", lambda e: self.send_cmd(self._command_payload("takeoff")))
        self.root.bind("<Escape>", lambda e: self.send_cmd(self._command_payload("land")))

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
            text="MJPEG frames are read in the background and fed into MediaPipe gesture detection.",
            justify="left",
        )
        info.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

    def _build_manual_controls_panel(self) -> None:
        controls = ttk.LabelFrame(self.main_frame, text="Manual Controller", padding=12)
        controls.pack(fill="x", pady=(0, 12))

        controls.columnconfigure((0, 1, 2), weight=1)

        ttk.Button(controls, text="⟲ CCW", command=lambda: self.send_cmd(self._command_payload("ccw", degrees=90))).grid(row=0, column=0, padx=6, pady=6, sticky="ew")
        ttk.Button(controls, text="↑ Forward", command=lambda: self.send_cmd(self._command_payload("forward", distance_cm=50))).grid(row=1, column=1, padx=6, pady=6, sticky="ew")
        ttk.Button(controls, text="⟳ CW", command=lambda: self.send_cmd(self._command_payload("cw", degrees=90))).grid(row=0, column=2, padx=6, pady=6, sticky="ew")
        ttk.Button(controls, text="← Left", command=lambda: self.send_cmd(self._command_payload("left", distance_cm=50))).grid(row=2, column=0, padx=6, pady=6, sticky="ew")
        ttk.Button(controls, text="TAKEOFF", command=lambda: self.send_cmd(self._command_payload("takeoff"))).grid(row=2, column=1, padx=6, pady=6, sticky="ew")
        ttk.Button(controls, text="→ Right", command=lambda: self.send_cmd(self._command_payload("right", distance_cm=50))).grid(row=2, column=2, padx=6, pady=6, sticky="ew")
        ttk.Button(controls, text="↓ Back", command=lambda: self.send_cmd(self._command_payload("back", distance_cm=50))).grid(row=3, column=1, padx=6, pady=6, sticky="ew")
        ttk.Button(controls, text="LAND", command=lambda: self.send_cmd(self._command_payload("land"))).grid(row=4, column=1, padx=6, pady=6, sticky="ew")
        ttk.Button(controls, text="EMERGENCY", command=lambda: self.send_cmd(self._command_payload("emergency"))).grid(row=5, column=0, columnspan=3, padx=6, pady=10, sticky="ew")

    def _build_gesture_controls_panel(self) -> None:
        frame = ttk.LabelFrame(self.main_frame, text="Gesture Control", padding=12)
        frame.pack(fill="x", pady=(0, 12))

        ttk.Checkbutton(
            frame,
            text="Enable Gesture Control",
            variable=self.gesture_enabled,
        ).grid(row=0, column=0, sticky="w", padx=8, pady=6)
        ttk.Label(frame, textvariable=self.gesture_status_var).grid(row=1, column=0, sticky="w", padx=8, pady=4)
        ttk.Label(frame, textvariable=self.raw_gesture_var).grid(row=1, column=1, sticky="w", padx=8, pady=4)
        ttk.Label(frame, textvariable=self.stable_gesture_var).grid(row=2, column=0, sticky="w", padx=8, pady=4)
        ttk.Label(frame, textvariable=self.last_queued_command_var).grid(row=2, column=1, sticky="w", padx=8, pady=4)
        ttk.Label(frame, textvariable=self.last_dispatched_gesture_var).grid(row=3, column=0, sticky="w", padx=8, pady=4)
        ttk.Label(frame, textvariable=self.dispatch_status_var).grid(row=3, column=1, sticky="w", padx=8, pady=4)
        ttk.Label(frame, textvariable=self.last_sent_command_var).grid(row=4, column=0, sticky="w", padx=8, pady=4)
        ttk.Label(frame, textvariable=self.command_pipeline_var).grid(row=4, column=1, sticky="w", padx=8, pady=4)

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

    def send_cmd(self, payload: str | dict[str, Any]) -> None:
        self._send_api_command(payload, source="manual")

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

    def _video_capture_loop(self) -> None:
        capture = None

        while self._video_running:
            try:
                if capture is None or not capture.isOpened():
                    capture = cv2.VideoCapture(self.video_var.get().strip())
                    if not capture.isOpened():
                        capture.release()
                        capture = None
                        time.sleep(1.0)
                        continue

                ok, frame = capture.read()
                if not ok or frame is None:
                    time.sleep(0.05)
                    continue

                with self._video_lock:
                    self._latest_frame = frame.copy()

            except Exception:
                time.sleep(0.2)

        if capture is not None:
            capture.release()

    def _get_latest_frame(self):
        with self._video_lock:
            if self._latest_frame is None:
                return None
            return self._latest_frame.copy()

    def _gesture_tick(self) -> None:
        try:
            if not self.gesture_enabled.get():
                self.gesture_status_var.set("Gesture: OFF")
                self.raw_gesture_var.set("Raw: -")
                self.stable_gesture_var.set("Stable: -")
                self.dispatch_status_var.set("Dispatch: disabled")
                self._reset_dispatch_lock()
                return

            frame = self._get_latest_frame()
            if frame is None:
                self.gesture_status_var.set("Gesture: NO VIDEO")
                self.raw_gesture_var.set("Raw: -")
                self.stable_gesture_var.set("Stable: -")
                self.dispatch_status_var.set("Dispatch: waiting for video")
                self._reset_dispatch_lock()
                return

            prediction = self.gesture_inference.process(frame=frame)
            raw_gesture = prediction.raw_gesture or "NONE"
            stable_gesture = prediction.stable_gesture or "NONE"

            self.gesture_status_var.set("Gesture: ON")
            self.raw_gesture_var.set(f"Raw: {raw_gesture}")
            self.stable_gesture_var.set(
                f"Stable: {stable_gesture} ({prediction.stable_for_ms} ms)"
            )
            self._log_raw_gesture(raw_gesture)
            self._update_stable_tracking(stable_gesture)

            if prediction.stable_gesture:
                self._dispatch_gesture_command(prediction.stable_gesture)
            else:
                self.dispatch_status_var.set("Dispatch: waiting for stable gesture")

        except Exception as exc:
            self.gesture_status_var.set(f"Gesture Error: {exc}")
            self.dispatch_status_var.set("Dispatch: inference error")
            self._reset_dispatch_lock()
        finally:
            self.root.after(400, self._gesture_tick)

    def _dispatch_gesture_command(self, stable_gesture: str) -> None:
        spec = self.gesture_mapper.map_gesture(stable_gesture)
        if spec is None:
            self._set_dispatch_blocked(stable_gesture, "no_command")
            return

        now = time.monotonic()
        payload = spec.to_payload()
        is_emergency = payload["command"] == "emergency"

        if self._last_dispatched_gesture == stable_gesture and not is_emergency:
            self._set_dispatch_blocked(stable_gesture, "duplicate")
            return

        if not is_emergency and (now - self._last_command_sent_at) < self.command_cooldown_seconds:
            self._set_dispatch_blocked(stable_gesture, "cooldown")
            return

        ok = self._send_api_command(payload, source="gesture")
        if not ok:
            self._set_dispatch_blocked(stable_gesture, "queue_error")
            return

        self._last_command_sent_at = now
        formatted = self._format_command_payload(payload)
        self._last_command_sent_value = formatted
        self._last_dispatched_gesture = stable_gesture
        self._last_blocked_signature = None
        self.last_sent_command_var.set(f"Last Command: {formatted}")
        self.last_dispatched_gesture_var.set(f"Last Gesture: {stable_gesture}")
        self.dispatch_status_var.set(f"Dispatch: sent {payload['command']}")
        self._debug_log("command dispatched", gesture=stable_gesture, command=formatted)

    def _send_api_command(self, payload: str | dict[str, Any], source: str = "manual") -> bool:
        normalized_payload = self._normalize_command_payload(payload)
        formatted = self._format_command_payload(normalized_payload)
        try:
            self._command_queue.put_nowait((normalized_payload, source))
            self.last_queued_command_var.set(f"Last Queued: {formatted}")
            self.command_pipeline_var.set("Command Queue: queued")
            return True
        except Exception:
            self.command_pipeline_var.set("Command Queue: enqueue failed")
            self._debug_log("command enqueue failed", source=source, command=formatted)
            return False

    def _command_worker_loop(self) -> None:
        while self._command_worker_running:
            try:
                task = self._command_queue.get(timeout=0.2)
            except Empty:
                continue

            if task is None:
                self._command_queue.task_done()
                break

            payload, source = task
            formatted = self._format_command_payload(payload)
            self.root.after(0, self.command_pipeline_var.set, f"Command Queue: sending {formatted}")

            try:
                response = self.http.post(
                    f"{self.api_base}/command",
                    json=payload,
                    timeout=2,
                )
                response.raise_for_status()
                self.root.after(0, self.last_sent_command_var.set, f"Last Command: {formatted}")
                self.root.after(0, self.command_pipeline_var.set, "Command Queue: idle")
                self._debug_log("command sent", source=source, command=formatted)
            except requests.RequestException:
                self.root.after(0, self.command_pipeline_var.set, "Command Queue: send failed")
                self._debug_log("command send failed", source=source, command=formatted)
            finally:
                self._command_queue.task_done()

    def _on_close(self) -> None:
        self._video_running = False
        self._command_worker_running = False
        self._command_queue.put_nowait(None)
        if self._video_thread.is_alive():
            self._video_thread.join(timeout=1.0)
        if self._command_worker_thread.is_alive():
            self._command_worker_thread.join(timeout=1.0)
        self.root.destroy()

    def _update_stable_tracking(self, stable_gesture: str) -> None:
        next_stable = None if stable_gesture == "NONE" else stable_gesture
        if next_stable == self._current_stable_gesture:
            return

        self._debug_log(
            "stable gesture transition",
            previous=self._current_stable_gesture or "NONE",
            current=stable_gesture,
        )
        self._current_stable_gesture = next_stable
        self._reset_dispatch_lock()

    def _reset_dispatch_lock(self) -> None:
        self._last_dispatched_gesture = None
        self._last_blocked_signature = None

    def _set_dispatch_blocked(self, gesture: str, reason: str) -> None:
        signature = (gesture, reason)
        self.dispatch_status_var.set(f"Dispatch: blocked ({reason})")
        if self._last_blocked_signature == signature:
            return
        self._last_blocked_signature = signature
        self._debug_log("command skipped", gesture=gesture, reason=reason)

    def _log_raw_gesture(self, raw_gesture: str) -> None:
        if raw_gesture == self._last_logged_raw_gesture:
            return
        self._last_logged_raw_gesture = raw_gesture
        self._debug_log("gesture detected", raw=raw_gesture)

    @staticmethod
    def _debug_log(message: str, **kwargs) -> None:
        detail = " ".join(f"{key}={value}" for key, value in kwargs.items())
        if detail:
            print(f"[Gesture] {message} | {detail}", flush=True)
        else:
            print(f"[Gesture] {message}", flush=True)

    @staticmethod
    def _command_payload(command: str, **args: Any) -> dict[str, Any]:
        payload = {"command": command}
        if args:
            payload["args"] = args
        return payload

    def _normalize_command_payload(self, payload: str | dict[str, Any]) -> dict[str, Any]:
        if isinstance(payload, str):
            return {"command": payload}

        normalized = {"command": str(payload["command"])}
        args = payload.get("args")
        if args:
            normalized["args"] = dict(args)
        return normalized

    @staticmethod
    def _format_command_payload(payload: dict[str, Any]) -> str:
        command = str(payload["command"])
        args = payload.get("args") or {}
        if not args:
            return command
        return f"{command} ({', '.join(f'{key}={value}' for key, value in args.items())})"
