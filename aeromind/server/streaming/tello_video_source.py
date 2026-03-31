from __future__ import annotations

from typing import Any

import cv2

from server.core.util.log import log


class TelloVideoSource:
    def __init__(
        self,
        drone,
        video_url: str,
        warmup_s: float = 0.8,
        watchdog_s: float = 2.5,
        stall_reads: int = 20,
    ):
        self.drone = drone
        self.video_url = video_url
        self.warmup_s = warmup_s
        self.watchdog_s = watchdog_s
        self.stall_reads = stall_reads

        self.cap: cv2.VideoCapture | None = None
        self._failed_reads = 0
        self._logged_first_frame = False
        self._stopping = False

    def start(self) -> bool:
        try:
            self._stopping = False
            if self.drone.enabled:
                log("[VIDEO]", "Requesting Tello stream", url=self.video_url)
                self.drone.send_command("streamon")

            self.release()
            self.cap = cv2.VideoCapture(self.video_url, cv2.CAP_FFMPEG)
            if not self.cap.isOpened():
                log("[VIDEO]", "Failed to open Tello video stream", url=self.video_url)
                return False

            self._logged_first_frame = False
            log("[VIDEO]", "Tello video stream started", url=self.video_url)
            return True
        except Exception as exc:
            log("[VIDEO]", "Error starting Tello video stream", error=exc)
            return False

    def read(self) -> tuple[bool, Any]:
        cap = self.cap
        if cap is None or self._stopping:
            return False, None

        try:
            ok, frame = cap.read()
        except cv2.error as exc:
            if not self._stopping:
                log("[VIDEO]", "OpenCV read failed", url=self.video_url, error=exc)
            return False, None
        except Exception as exc:
            if not self._stopping:
                log("[VIDEO]", "Video read failed", url=self.video_url, error=exc)
            return False, None

        if self._stopping or self.cap is None:
            return False, None

        if not ok or frame is None:
            self._failed_reads += 1
            if self._failed_reads == 1 and not self._stopping:
                log("[VIDEO]", "Tello video frame read failed", url=self.video_url)
            if self._failed_reads >= self.stall_reads and not self._stopping:
                log("[VIDEO]", "Stalled stream detected", failed_reads=self._failed_reads)
                self.restart_stream()
            return False, None

        self._failed_reads = 0
        if not self._logged_first_frame:
            self._logged_first_frame = True
            log("[VIDEO]", "Tello video frames received", url=self.video_url)
        return True, frame

    def restart_stream(self) -> bool:
        if self._stopping:
            return False
        log("[VIDEO]", "Restarting Tello video stream")
        self.release()
        return self.start()

    def release(self) -> None:
        self._stopping = True
        cap = self.cap
        self.cap = None
        if cap is not None:
            try:
                cap.release()
            except cv2.error:
                pass
        self._logged_first_frame = False
        self._failed_reads = 0
