from __future__ import annotations

from dataclasses import dataclass

from app.models.video_source import VideoSourceSpec

API_BASE = "http://127.0.0.1:5000/api"
STATUS_REFRESH_MS = 1000
VIDEO_URL = "http://127.0.0.1:8080/video"
SIM_WEBCAM_INDEX = 0
VIDEO_RECONNECT_DELAY_MS = 1000
VIDEO_READ_INTERVAL_MS = 30
VIDEO_MAX_WIDTH: int | None = None
VIDEO_MAX_HEIGHT: int | None = None
VIDEO_DROP_FRAMES_ON_RECONNECT = 3
VIDEO_BACKEND_PREFER_FFMPEG = True
GESTURE_INFERENCE_MAX_FPS = 12
GESTURE_LOG_FLUSH_ROWS = 50
PERFORMANCE_LOG_INTERVAL_MS = 5000
DEBUG_BYPASS_STABILITY = False
DEBUG_BYPASS_MIN_CONFIDENCE = 0.55
INFERENCE_INPUT_WIDTH = 320
INFERENCE_INPUT_HEIGHT = 240
INFERENCE_PROCESS_EVERY_NTH_FRAME = 1
INFERENCE_MAX_PENDING_FRAMES = 1


@dataclass(slots=True)
class AppConfig:
    api_base_url: str = API_BASE
    video_url: str = VIDEO_URL
    sim_webcam_index: int = SIM_WEBCAM_INDEX
    status_refresh_ms: int = STATUS_REFRESH_MS
    video_reconnect_delay_ms: int = VIDEO_RECONNECT_DELAY_MS
    video_read_interval_ms: int = VIDEO_READ_INTERVAL_MS
    video_max_width: int | None = VIDEO_MAX_WIDTH
    video_max_height: int | None = VIDEO_MAX_HEIGHT
    video_drop_frames_on_reconnect: int = VIDEO_DROP_FRAMES_ON_RECONNECT
    video_backend_prefer_ffmpeg: bool = VIDEO_BACKEND_PREFER_FFMPEG
    gesture_inference_max_fps: int = GESTURE_INFERENCE_MAX_FPS
    gesture_log_flush_rows: int = GESTURE_LOG_FLUSH_ROWS
    performance_log_interval_ms: int = PERFORMANCE_LOG_INTERVAL_MS
    debug_bypass_stability: bool = DEBUG_BYPASS_STABILITY
    debug_bypass_min_confidence: float = DEBUG_BYPASS_MIN_CONFIDENCE
    inference_input_width: int = INFERENCE_INPUT_WIDTH
    inference_input_height: int = INFERENCE_INPUT_HEIGHT
    inference_process_every_nth_frame: int = INFERENCE_PROCESS_EVERY_NTH_FRAME
    inference_max_pending_frames: int = INFERENCE_MAX_PENDING_FRAMES

    def drone_video_source(self) -> VideoSourceSpec:
        return VideoSourceSpec.mjpeg(self.video_url)

    def sim_video_source(self) -> VideoSourceSpec:
        return VideoSourceSpec.webcam(self.sim_webcam_index)

    def gesture_inference_interval_ms(self) -> int:
        fps = max(1, int(self.gesture_inference_max_fps))
        return max(1, int(1000 / fps))
