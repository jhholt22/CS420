from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


DetectorStatus = Literal[
    "detector_ready",
    "detector_missing_dependency",
    "detector_init_failed",
    "detector_unavailable",
]


@dataclass(slots=True)
class GestureInferenceResult:
    raw_gesture: str | None
    stable_gesture: str | None
    confidence: float | None
    command_name: str | None
    queue_state: str
    stable_hits: int
    required_hits: int
    required_confidence: float
    detector_available: bool
    detector_status: DetectorStatus
    detector_error: str | None
    detector_model_path: str | None


@dataclass(slots=True)
class RawGestureSample:
    recognizer_label: str | None
    mapped_gesture: str | None
    confidence: float | None
    tilt_value: float | None
    raw_direction: str | None
    index_mcp_x: float | None
    index_tip_x: float | None
