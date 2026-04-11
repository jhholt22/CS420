from __future__ import annotations

from dataclasses import asdict
from typing import Any

from app.config import AppConfig
from app.models.startup_check import StartupCheckItem, StartupSummary
from app.models.video_source import VideoSourceSpec
from app.services.api_client import ApiClient, ApiClientError
from app.services.gesture_inference_service import GestureInferenceService
from app.services.video_stream_service import VideoStreamService
from app.utils.logging_utils import gesture_debug_log


class StartupSmokeCheckService:
    def __init__(
        self,
        *,
        config: AppConfig,
        api_client: ApiClient,
        gesture_inference_service: GestureInferenceService,
        video_stream_service: VideoStreamService,
    ) -> None:
        self.config = config
        self.api_client = api_client
        self.gesture_inference_service = gesture_inference_service
        self.video_stream_service = video_stream_service

    def run(self) -> StartupSummary:
        items = [
            self._check_detector_dependency(),
            self._check_detector_init(),
        ]

        api_item, status_payload, diag_payload = self._check_api()
        items.append(api_item)

        items.append(self._check_drone_sdk(status_payload, diag_payload))
        items.append(self._check_video_stream(status_payload))

        summary = StartupSummary(items=items)
        gesture_debug_log(
            "startup.smoke_check",
            overall_status=summary.overall_status,
            summary=[asdict(item) for item in summary.items],
        )
        return summary

    def _check_detector_dependency(self) -> StartupCheckItem:
        error = self.gesture_inference_service.get_detector_error()
        status = self.gesture_inference_service.get_detector_status()
        if status == "detector_missing_dependency":
            return StartupCheckItem(
                subsystem="detector_dependency",
                status="failed",
                reason=error or "MediaPipe dependency is missing",
                next_action="Install the missing detector dependency and restart the UI.",
            )
        return StartupCheckItem(
            subsystem="detector_dependency",
            status="ok",
            reason="Detector dependency is available.",
            next_action="None.",
        )

    def _check_detector_init(self) -> StartupCheckItem:
        status = self.gesture_inference_service.get_detector_status()
        error = self.gesture_inference_service.get_detector_error()
        if status == "detector_ready":
            return StartupCheckItem(
                subsystem="detector_initialization",
                status="ok",
                reason="Detector initialized successfully.",
                next_action="None.",
            )
        severity = "failed" if status == "detector_init_failed" else "warning"
        return StartupCheckItem(
            subsystem="detector_initialization",
            status=severity,
            reason=error or status,
            next_action="Check detector model path and MediaPipe installation.",
        )

    def _check_api(self) -> tuple[StartupCheckItem, dict[str, Any] | None, dict[str, Any] | None]:
        try:
            status_payload = self.api_client.get_status()
        except ApiClientError as exc:
            return (
                StartupCheckItem(
                    subsystem="api",
                    status="warning",
                    reason=str(exc),
                    next_action="Start the AeroMind backend if you need live drone or sim control.",
                ),
                None,
                None,
            )

        diag_payload: dict[str, Any] | None = None
        if status_payload.get("running"):
            try:
                diag_payload = self.api_client.get_diag()
            except ApiClientError as exc:
                return (
                    StartupCheckItem(
                        subsystem="api",
                        status="warning",
                        reason=f"Backend reachable but diagnostics failed: {exc}",
                        next_action="Verify the backend controller is healthy and the /diag endpoint responds.",
                    ),
                    status_payload,
                    None,
                )

        mode = str(status_payload.get("mode") or "--")
        if status_payload.get("running"):
            return (
                StartupCheckItem(
                    subsystem="api",
                    status="ok",
                    reason=f"Backend reachable in mode={mode}.",
                    next_action="None.",
                ),
                status_payload,
                diag_payload,
            )

        return (
            StartupCheckItem(
                subsystem="api",
                status="warning",
                reason="Backend reachable but controller is not running.",
                next_action="Use Start SIM or Start DRONE before sending commands.",
            ),
            status_payload,
            diag_payload,
        )

    def _check_drone_sdk(
        self,
        status_payload: dict[str, Any] | None,
        diag_payload: dict[str, Any] | None,
    ) -> StartupCheckItem:
        mode = str((status_payload or {}).get("mode") or "--").lower()
        running = bool((status_payload or {}).get("running"))
        if mode != "drone" or not running:
            return StartupCheckItem(
                subsystem="drone_sdk",
                status="ok",
                reason="Drone SDK check skipped because runtime is not in drone mode.",
                next_action="Start the backend in DRONE mode to validate Tello startup.",
            )

        if diag_payload and diag_payload.get("sdk_mode"):
            return StartupCheckItem(
                subsystem="drone_sdk",
                status="ok",
                reason="Drone SDK handshake succeeded.",
                next_action="None.",
            )

        return StartupCheckItem(
            subsystem="drone_sdk",
            status="failed",
            reason="Backend is in drone mode but SDK handshake is not ready.",
            next_action="Check Tello power/Wi-Fi and rerun the drone startup path.",
        )

    def _check_video_stream(self, status_payload: dict[str, Any] | None) -> StartupCheckItem:
        mode = str((status_payload or {}).get("mode") or "--").lower()
        running = bool((status_payload or {}).get("running"))
        source = self._video_source_for_mode(mode)
        reachable = self.video_stream_service.probe_stream(source)

        if reachable:
            return StartupCheckItem(
                subsystem="video_stream",
                status="ok",
                reason=f"Video source is reachable for {source.label}.",
                next_action="None.",
            )

        if not running:
            return StartupCheckItem(
                subsystem="video_stream",
                status="warning",
                reason="Video stream is not reachable because the backend controller is not running yet.",
                next_action="Start the backend controller, then rerun the smoke check.",
            )

        if mode == "drone":
            return StartupCheckItem(
                subsystem="video_stream",
                status="warning",
                reason="Drone mode is active but the MJPEG/video stream is not reachable yet.",
                next_action="Wait for stream startup or inspect Tello video logs if it never becomes ready.",
            )
        if mode == "sim":
            return StartupCheckItem(
                subsystem="video_stream",
                status="warning",
                reason=f"SIM mode is active but {source.label} is not producing frames yet.",
                next_action="Verify the configured webcam index is correct and not in use by another app.",
            )

        return StartupCheckItem(
            subsystem="video_stream",
            status="warning",
            reason="Video stream endpoint is not reachable yet.",
            next_action="Verify the MJPEG server is running on the configured video URL.",
        )

    def _video_source_for_mode(self, mode: str | None) -> VideoSourceSpec:
        normalized_mode = self._normalize_mode(mode)
        # The gesture camera is a separate pipeline; the main runtime/smoke check video
        # source must follow the active sim/drone transport instead of the gesture webcam.
        if normalized_mode == "sim":
            return self.config.sim_video_source()
        return self.config.drone_video_source()

    @staticmethod
    def _normalize_mode(mode: str | None) -> str | None:
        if mode is None:
            return None
        normalized = str(mode).strip().lower()
        if not normalized or normalized == "--":
            return None
        return normalized


def run_startup_smoke_check(config: AppConfig | None = None) -> StartupSummary:
    cfg = config or AppConfig()
    api_client = ApiClient(cfg.api_base_url)
    gesture_service = GestureInferenceService()
    video_service = VideoStreamService(
        cfg.drone_video_source(),
        prefer_ffmpeg=cfg.video_backend_prefer_ffmpeg,
        max_width=cfg.video_max_width,
        max_height=cfg.video_max_height,
    )
    service = StartupSmokeCheckService(
        config=cfg,
        api_client=api_client,
        gesture_inference_service=gesture_service,
        video_stream_service=video_service,
    )
    return service.run()


def main() -> int:
    summary = run_startup_smoke_check()
    print(f"overall_status={summary.overall_status}")
    for item in summary.items:
        print(f"{item.subsystem}: {item.status} | reason={item.reason} | next={item.next_action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
