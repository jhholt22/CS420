from __future__ import annotations

import tkinter as tk


class AppUiVars:
    def __init__(self, root: tk.Misc, video_url: str) -> None:
        self.status_var = tk.StringVar(root, value="Unknown")
        self.mode_var = tk.StringVar(root, value="-")
        self.flight_var = tk.StringVar(root, value="-")
        self.battery_var = tk.StringVar(root, value="-")
        self.height_var = tk.StringVar(root, value="-")

        self.video_var = tk.StringVar(root, value=video_url)

        self.gesture_enabled = tk.BooleanVar(root, value=False)
        self.gesture_status_var = tk.StringVar(root, value="Gesture: OFF")
        self.raw_gesture_var = tk.StringVar(root, value="Raw: -")
        self.stable_gesture_var = tk.StringVar(root, value="Stable: -")
        self.last_queued_command_var = tk.StringVar(root, value="Last Queued: -")
        self.last_sent_command_var = tk.StringVar(root, value="Last Command: -")
        self.last_dispatched_gesture_var = tk.StringVar(root, value="Last Gesture: -")
        self.dispatch_status_var = tk.StringVar(root, value="Dispatch: idle")
        self.command_pipeline_var = tk.StringVar(root, value="Command Queue: idle")

        self.left_stick_var = tk.StringVar(root, value="Left Stick: yaw=0 up/down=0")
        self.right_stick_var = tk.StringVar(root, value="Right Stick: left/right=0 forward/back=0")
        self.rc_status_var = tk.StringVar(root, value="RC: idle")