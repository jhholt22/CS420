from __future__ import annotations

import threading
import time
import tkinter as tk
from queue import Empty, Queue
from typing import Any

import cv2
import requests
from PIL import Image, ImageTk

from clients.python_ui.app.gesture.inference import GestureInference
from clients.python_ui.app.gesture.mapper import GestureCommandMapper
from clients.python_ui.app.ui.app_styles import configure_app_styles
from clients.python_ui.app.ui.app_window import AppWindow
from clients.python_ui.app.ui.ui_vars import AppUiVars

API_BASE = "http://127.0.0.1:5000/api"
VIDEO_URL = "http://127.0.0.1:8080/video"
RC_SEND_INTERVAL_MS = 80


class AeroMindClientApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("AeroMind Python UI")
        self.root.geometry("980x860")
        self.root.minsize(920, 760)

        self.style = configure_app_styles(self.root)

        self.api_base = API_BASE
        self.http = requests.Session()

        self.ui_vars = AppUiVars(self.root, VIDEO_URL)

        self.status_var = self.ui_vars.status_var
        self.mode_var = self.ui_vars.mode_var
        self.flight_var = self.ui_vars.flight_var
        self.battery_var = self.ui_vars.battery_var
        self.height_var = self.ui_vars.height_var
        self.video_var = self.ui_vars.video_var

        self.gesture_enabled = self.ui_vars.gesture_enabled
        self.gesture_status_var = self.ui_vars.gesture_status_var
        self.raw_gesture_var = self.ui_vars.raw_gesture_var
        self.stable_gesture_var = self.ui_vars.stable_gesture_var
        self.last_queued_command_var = self.ui_vars.last_queued_command_var
        self.last_sent_command_var = self.ui_vars.last_sent_command_var
        self.last_dispatched_gesture_var = self.ui_vars.last_dispatched_gesture_var
        self.dispatch_status_var = self.ui_vars.dispatch_status_var
        self.command_pipeline_var = self.ui_vars.command_pipeline_var
        self.left_stick_var = self.ui_vars.left_stick_var
        self.right_stick_var = self.ui_vars.right_stick_var
        self.rc_status_var = self.ui_vars.rc_status_var

        self.gesture_mapper = GestureCommandMapper()
        self.gesture_inference = GestureInference(stability_ms=1200)

        self.command_cooldown_seconds = 2.0
        self._last_command_sent_at = 0.0
        self._current_stable_gesture: str | None = None
        self._last_dispatched_gesture: str | None = None
        self._last_blocked_signature: tuple[str | None, str] | None = None
        self._last_logged_raw_gesture: str | None = None

        self._status_refresh_in_progress = False
        self._rc_values = {
            "left_right": 0,
            "forward_back": 0,
            "up_down": 0,
            "yaw": 0,
        }
        self._last_sent_rc_values: dict[str, int] | None = None
        self._latest_rc_task: tuple[dict[str, Any], str] | None = None
        self._rc_task_lock = threading.Lock()

        self._video_lock = threading.Lock()
        self._latest_frame = None
        self._preview_photo = None
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
        self.root.after(RC_SEND_INTERVAL_MS, self._rc_send_tick)
        self.root.after(50, self._video_preview_tick)
        self.root.after(1000, self._status_tick)

    def _build_ui(self) -> None:
        self.app_window = AppWindow(
            self.root,
            self.ui_vars,
            on_refresh=self._refresh_status_async,
            on_start_sim=lambda: self.start_controller("sim"),
            on_start_drone=lambda: self.start_controller("drone"),
            on_stop=self.stop_controller,
            on_left_stick_change=self._on_left_stick_change,
            on_right_stick_change=self._on_right_stick_change,
            on_takeoff=lambda: self.send_cmd(self._command_payload("takeoff")),
            on_land=lambda: self.send_cmd(self._command_payload("land")),
            on_emergency=lambda: self.send_cmd(self._command_payload("emergency")),
        )

        self.main_frame = self.app_window.main_frame
        self.status_panel = self.app_window.status_panel
        self.action_panel = self.app_window.action_panel
        self.video_panel = self.app_window.video_panel
        self.manual_control_panel = self.app_window.manual_control_panel
        self.gesture_panel = self.app_window.gesture_panel

        self.video_preview_label = self.video_panel.preview_label
        self.left_stick = self.manual_control_panel.left_stick
        self.right_stick = self.manual_control_panel.right_stick

    def _bind_keys(self) -> None:
        self.root.bind("<space>", lambda e: self.send_cmd(self._command_payload("takeoff")))
        self.root.bind("<Escape>", lambda e: self.send_cmd(self._command_payload("land")))

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

    def _video_preview_tick(self) -> None:
        try:
            frame = self._get_latest_frame()
            if frame is None:
                if self._preview_photo is None:
                    self.video_panel.set_waiting()
                return

            preview = cv2.resize(frame, (480, 270))
            preview = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)
            photo = ImageTk.PhotoImage(Image.fromarray(preview))
            self._preview_photo = photo
            self.video_panel.set_preview_image(photo)

        except Exception:
            self._preview_photo = None
            self.video_panel.set_unavailable()
        finally:
            if self.root.winfo_exists():
                self.root.after(50, self._video_preview_tick)

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
            self.stable_gesture_var.set(f"Stable: {stable_gesture} ({prediction.stable_for_ms} ms)")
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
        self._last_dispatched_gesture = stable_gesture
        self._last_blocked_signature = None
        self.last_sent_command_var.set(f"Last Command: {formatted}")
        self.last_dispatched_gesture_var.set(f"Last Gesture: {stable_gesture}")
        self.dispatch_status_var.set(f"Dispatch: sent {payload['command']}")
        self._debug_log("command dispatched", gesture=stable_gesture, command=formatted)

    def _on_left_stick_change(self, yaw: int, up_down: int) -> None:
        self._rc_values["yaw"] = yaw
        self._rc_values["up_down"] = up_down
        self._update_rc_labels()

    def _on_right_stick_change(self, left_right: int, forward_back: int) -> None:
        self._rc_values["left_right"] = left_right
        self._rc_values["forward_back"] = forward_back
        self._update_rc_labels()

    def _update_rc_labels(self) -> None:
        self.left_stick_var.set(
            f"Left Stick: yaw={self._rc_values['yaw']} up/down={self._rc_values['up_down']}"
        )
        self.right_stick_var.set(
            f"Right Stick: left/right={self._rc_values['left_right']} forward/back={self._rc_values['forward_back']}"
        )

    def _rc_send_tick(self) -> None:
        try:
            rc_args = dict(self._rc_values)
            active = any(rc_args.values())
            last_active = bool(self._last_sent_rc_values and any(self._last_sent_rc_values.values()))

            if active or last_active:
                payload = self._command_payload("rc", **rc_args)
                if self._send_api_command(payload, source="manual-rc"):
                    self.rc_status_var.set(f"RC: queued {self._format_command_payload(payload)}")
                else:
                    self.rc_status_var.set("RC: enqueue failed")
            else:
                self.rc_status_var.set("RC: idle")
        finally:
            self.root.after(RC_SEND_INTERVAL_MS, self._rc_send_tick)

    def _send_api_command(self, payload: str | dict[str, Any], source: str = "manual") -> bool:
        normalized_payload = self._normalize_command_payload(payload)
        formatted = self._format_command_payload(normalized_payload)

        if normalized_payload["command"] == "rc":
            with self._rc_task_lock:
                self._latest_rc_task = (normalized_payload, source)
            self.last_queued_command_var.set(f"Last Queued: {formatted}")
            self.command_pipeline_var.set("Command Queue: rc ready")
            return True

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
            task, from_queue = self._next_command_task()
            if task is None:
                if from_queue:
                    self._command_queue.task_done()
                    break
                continue

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
                if payload["command"] == "rc":
                    self._last_sent_rc_values = dict(payload.get("args") or {})
                    self.root.after(0, self.rc_status_var.set, f"RC: sent {formatted}")
                self._debug_log("command sent", source=source, command=formatted)
            except requests.RequestException:
                self.root.after(0, self.command_pipeline_var.set, "Command Queue: send failed")
                if payload["command"] == "rc":
                    self.root.after(0, self.rc_status_var.set, "RC: send failed")
                self._debug_log("command send failed", source=source, command=formatted)
            finally:
                if from_queue:
                    self._command_queue.task_done()

    def _next_command_task(self) -> tuple[tuple[dict[str, Any], str] | None, bool]:
        try:
            task = self._command_queue.get(timeout=0.05)
            got_queue_item = True
        except Empty:
            got_queue_item = False
            task = None

        if got_queue_item:
            if task is None:
                return None, True
            return task, True

        if task is None:
            with self._rc_task_lock:
                if self._latest_rc_task is None:
                    return None, False
                rc_task = self._latest_rc_task
                self._latest_rc_task = None
                return rc_task, False

        return None, False

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