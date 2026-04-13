from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = [
    "ApiClient",
    "ApiClientError",
    "GestureInferenceResult",
    "GestureInferenceService",
    "TelemetryService",
    "VideoStreamService",
]

if TYPE_CHECKING:
    from app.gestures.types import GestureInferenceResult
    from app.services.api_client import ApiClient, ApiClientError
    from app.services.gesture_inference_service import GestureInferenceService
    from app.services.telemetry_service import TelemetryService
    from app.services.video_stream_service import VideoStreamService


def __getattr__(name: str) -> Any:
    if name in {"ApiClient", "ApiClientError"}:
        from app.services.api_client import ApiClient, ApiClientError

        return {"ApiClient": ApiClient, "ApiClientError": ApiClientError}[name]
    if name == "GestureInferenceResult":
        from app.gestures.types import GestureInferenceResult

        return GestureInferenceResult
    if name == "GestureInferenceService":
        from app.services.gesture_inference_service import GestureInferenceService

        return GestureInferenceService
    if name == "TelemetryService":
        from app.services.telemetry_service import TelemetryService

        return TelemetryService
    if name == "VideoStreamService":
        from app.services.video_stream_service import VideoStreamService

        return VideoStreamService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
