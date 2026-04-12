from __future__ import annotations

from dataclasses import dataclass, field

from app.gestures.registry import get_gesture_definition
from app.models.video_source import VideoSourceSpec

API_BASE = "http://127.0.0.1:5000/api"
STATUS_REFRESH_MS = 1000
VIDEO_URL = "http://127.0.0.1:8080/video"

# Keep this 0 unless you really have a second camera dedicated to gestures.
SIM_WEBCAM_INDEX = 0
GESTURE_WEBCAM_INDEX = 0

VIDEO_RECONNECT_DELAY_MS = 1000
VIDEO_READ_INTERVAL_MS = 40
VIDEO_MAX_WIDTH: int | None = None
VIDEO_MAX_HEIGHT: int | None = None
VIDEO_DROP_FRAMES_ON_RECONNECT = 3
VIDEO_BACKEND_PREFER_FFMPEG = True

GESTURE_LOG_FLUSH_ROWS = 50
PERFORMANCE_LOG_INTERVAL_MS = 5000


@dataclass(slots=True)
class GestureThresholdConfig:
    # Gesture confidence gates for inference readiness live here.
    default_min_confidence: float = 0.65
    noise_confidence_floor: float = 0.50

    def min_confidence_for_gesture(self, gesture_name: str | None) -> float:
        gesture = get_gesture_definition(gesture_name)
        if gesture is None:
            return self.default_min_confidence
        return float(gesture.confidence)


@dataclass(slots=True)
class GestureStabilityConfig:
    # Gesture stabilization and controller-side debounce live here.
    stability_frames: int = 3
    dominance_frames: int = 2
    one_shot_stabilization_ms: int = 320
    movement_stabilization_ms: int = 160
    stability_reset_debounce_ms: int = 220

    # More forgiving so one-shot gestures do not get released instantly on hand loss.
    release_window_ms: int = 650
    hover_stop_grace_ms: int = 650
    hover_command_cooldown_ms: int = 1000

    def stabilization_ms_for_gesture(self, gesture_name: str | None, *, behavior_type: str | None) -> int:
        gesture = get_gesture_definition(gesture_name)
        if gesture is not None:
            return int(gesture.stabilization)
        if behavior_type == "one_shot":
            return int(self.one_shot_stabilization_ms)
        return int(self.movement_stabilization_ms)


@dataclass(slots=True)
class GestureMotionConfig:
    # Continuous movement resend/cooldown and RC command shaping live here.
    movement_resend_interval_ms: int = 150
    movement_cooldown_ms: int = 140
    movement_fast_path_confidence: float = 0.85
    default_rc_speed: int = 40
    forward_rc_speed: int = 35
    left_right_rc_speed: int = 35
    yaw_rc_speed: int = 30
    per_command_rc_speed: dict[str, int] = field(default_factory=dict)
    move_distance_cm: int = 50
    rotation_degrees: int = 90

    def fast_path_confidence_for_gesture(self, gesture_name: str | None) -> float:
        return float(self.movement_fast_path_confidence)

    def rc_speed_for_command(self, command_name: str) -> int:
        if command_name in self.per_command_rc_speed:
            return int(self.per_command_rc_speed[command_name])
        if command_name in {"forward", "back"}:
            return int(self.forward_rc_speed)
        if command_name in {"left", "right"}:
            return int(self.left_right_rc_speed)
        if command_name in {"rotate_left", "rotate_right"}:
            return int(self.yaw_rc_speed)
        return int(self.default_rc_speed)


@dataclass(slots=True)
class GestureTerminalConfig:
    # Terminal one-shot latching and duplicate suppression live here.
    terminal_command_latch_enabled: bool = True
    terminal_command_cooldown_ms: int = 4000

    # Critical fix:
    # terminal commands should not require the hand to remain visible
    # because land/takeoff naturally make the frame change.
    terminal_command_release_required: bool = False


@dataclass(slots=True)
class GestureEnvironmentConfig:
    # Environment-dependent gesture reliability limits live here.
    max_reliable_distance_m: float = 1.5
    distance_compensation_enabled: bool = False


@dataclass(slots=True)
class GestureInferenceConfig:
    # Camera/inference throughput and detector bypass knobs live here.
    max_fps: int = 25
    input_width: int = 320
    input_height: int = 240
    process_every_nth_frame: int = 1
    max_pending_frames: int = 1
    max_num_hands: int = 1
    debug_bypass_stability: bool = False
    debug_bypass_min_confidence: float = 0.55


@dataclass(slots=True)
class AppConfig:
    api_base_url: str = API_BASE
    video_url: str = VIDEO_URL
    sim_webcam_index: int = SIM_WEBCAM_INDEX
    gesture_webcam_index: int = GESTURE_WEBCAM_INDEX
    status_refresh_ms: int = STATUS_REFRESH_MS
    video_reconnect_delay_ms: int = VIDEO_RECONNECT_DELAY_MS
    video_read_interval_ms: int = VIDEO_READ_INTERVAL_MS
    video_max_width: int | None = VIDEO_MAX_WIDTH
    video_max_height: int | None = VIDEO_MAX_HEIGHT
    video_drop_frames_on_reconnect: int = VIDEO_DROP_FRAMES_ON_RECONNECT
    video_backend_prefer_ffmpeg: bool = VIDEO_BACKEND_PREFER_FFMPEG
    gesture_log_flush_rows: int = GESTURE_LOG_FLUSH_ROWS
    performance_log_interval_ms: int = PERFORMANCE_LOG_INTERVAL_MS

    gesture_thresholds: GestureThresholdConfig = field(default_factory=GestureThresholdConfig)
    gesture_stability: GestureStabilityConfig = field(default_factory=GestureStabilityConfig)
    gesture_motion: GestureMotionConfig = field(default_factory=GestureMotionConfig)
    gesture_terminal: GestureTerminalConfig = field(default_factory=GestureTerminalConfig)
    gesture_environment: GestureEnvironmentConfig = field(default_factory=GestureEnvironmentConfig)
    gesture_inference: GestureInferenceConfig = field(default_factory=GestureInferenceConfig)

    def drone_video_source(self) -> VideoSourceSpec:
        return VideoSourceSpec.mjpeg(self.video_url)

    def sim_video_source(self) -> VideoSourceSpec:
        return VideoSourceSpec.webcam(self.sim_webcam_index)

    def gesture_video_source(self) -> VideoSourceSpec:
        return VideoSourceSpec.webcam(self.gesture_webcam_index)

    def gesture_inference_interval_ms(self) -> int:
        fps = max(1, int(self.gesture_inference.max_fps))
        return max(1, int(1000 / fps))

    def gesture_min_confidence(self, gesture_name: str | None) -> float:
        return self.gesture_thresholds.min_confidence_for_gesture(gesture_name)

    def gesture_stabilization_ms(self, gesture_name: str | None) -> int:
        gesture = get_gesture_definition(gesture_name)
        behavior_type = gesture.behavior_type if gesture is not None else None
        return self.gesture_stability.stabilization_ms_for_gesture(
            gesture_name,
            behavior_type=behavior_type,
        )

    def gesture_fast_path_confidence(self, gesture_name: str | None) -> float:
        return self.gesture_motion.fast_path_confidence_for_gesture(gesture_name)

    def gesture_rc_speed_for_command(self, command_name: str) -> int:
        return self.gesture_motion.rc_speed_for_command(command_name)

    @property
    def gesture_idle_hover_ms(self) -> int:
        return self.gesture_stability.hover_stop_grace_ms

    @property
    def gesture_hover_command_cooldown_ms(self) -> int:
        return self.gesture_stability.hover_command_cooldown_ms

    @property
    def gesture_inference_max_fps(self) -> int:
        return self.gesture_inference.max_fps

    @property
    def debug_bypass_stability(self) -> bool:
        return self.gesture_inference.debug_bypass_stability

    @property
    def debug_bypass_min_confidence(self) -> float:
        return self.gesture_inference.debug_bypass_min_confidence

    @property
    def gesture_move_distance_cm(self) -> int:
        return self.gesture_motion.move_distance_cm

    @property
    def gesture_rotation_degrees(self) -> int:
        return self.gesture_motion.rotation_degrees

    @property
    def gesture_one_shot_stabilization_ms(self) -> int:
        return self.gesture_stability.one_shot_stabilization_ms

    @property
    def gesture_movement_stabilization_ms(self) -> int:
        return self.gesture_stability.movement_stabilization_ms

    @property
    def gesture_movement_resend_interval_ms(self) -> int:
        return self.gesture_motion.movement_resend_interval_ms

    @property
    def gesture_movement_cooldown_ms(self) -> int:
        return self.gesture_motion.movement_cooldown_ms

    @property
    def gesture_movement_fast_path_confidence(self) -> float:
        return self.gesture_motion.movement_fast_path_confidence

    @property
    def gesture_movement_rc_speed(self) -> int:
        return self.gesture_motion.default_rc_speed

    @property
    def inference_input_width(self) -> int:
        return self.gesture_inference.input_width

    @property
    def inference_input_height(self) -> int:
        return self.gesture_inference.input_height

    @property
    def inference_process_every_nth_frame(self) -> int:
        return self.gesture_inference.process_every_nth_frame

    @property
    def inference_max_pending_frames(self) -> int:
        return self.gesture_inference.max_pending_frames
