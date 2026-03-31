from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RuntimeConfig:
    run_id: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"))

    enable_server_gesture_pipeline: bool = False

    conf_threshold: float = 0.80
    stable_window_ms: int = 400
    command_cooldown_ms: int = 900

    lighting: str = "normal"
    background: str = "clean"
    distance_m: float = 0.5

    api_host: str = "127.0.0.1"
    api_port: int = 5000

    mjpeg_host: str = "127.0.0.1"
    mjpeg_port: int = 8080
    mjpeg_fps: int = 12
    mjpeg_jpeg_quality: int = 80

    tello_ip: str = "192.168.10.1"
    tello_cmd_port: int = 8889
    tello_state_port: int = 8890
    tello_video_url: str = "udp://0.0.0.0:11111"
    local_cmd_port: int = 9000
    cmd_timeout_s: float = 2.5
    motion_command_cooldown_ms: int = 900
    motion_command_timeout_s: float = 1.0

    video_warmup_s: float = 0.8
    video_watchdog_s: float = 2.5
    video_stall_reads: int = 20
