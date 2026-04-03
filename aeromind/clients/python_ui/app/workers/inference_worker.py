from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock
from time import monotonic
from typing import Any

import cv2
from PySide6.QtCore import QObject, Signal

from app.services.gesture_inference_service import GestureInferenceResult, GestureInferenceService
from app.utils.logging_utils import gesture_debug_log


@dataclass(slots=True)
class InferenceUpdate:
    result: GestureInferenceResult
    freshness_ms: int
    processing_ms: float
    input_shape: tuple[int, ...] | None
    inference_shape: tuple[int, ...] | None


class LatestFrameBuffer:
    def __init__(self, max_pending_frames: int = 1) -> None:
        self.max_pending_frames = 1 if int(max_pending_frames) != 1 else 1
        self._lock = Lock()
        self._latest_frame: Any | None = None
        self._latest_submitted_at = 0.0
        self._dropped_frames = 0

    def submit(self, frame: Any) -> None:
        submitted_at = monotonic()
        with self._lock:
            # Real-time path: keep only the newest frame and drop any older pending frame.
            if self._latest_frame is not None:
                self._dropped_frames += 1
            self._latest_frame = frame
            self._latest_submitted_at = submitted_at

    def take_latest(self) -> tuple[Any, float] | None:
        with self._lock:
            if self._latest_frame is None:
                return None
            frame = self._latest_frame
            submitted_at = self._latest_submitted_at
            self._latest_frame = None
            self._latest_submitted_at = 0.0
        return frame, submitted_at

    def clear(self) -> None:
        with self._lock:
            self._latest_frame = None
            self._latest_submitted_at = 0.0
            self._dropped_frames = 0

    def pending_count(self) -> int:
        with self._lock:
            return 1 if self._latest_frame is not None else 0

    def pending_age_ms(self) -> int | None:
        with self._lock:
            if self._latest_frame is None or self._latest_submitted_at <= 0.0:
                return None
            return max(0, int((monotonic() - self._latest_submitted_at) * 1000.0))

    def take_dropped_count(self) -> int:
        with self._lock:
            dropped = self._dropped_frames
            self._dropped_frames = 0
        return dropped


class InferenceWorker(QObject):
    inferenceReady = Signal(object)
    workerStarted = Signal()
    workerFinished = Signal()

    def __init__(
        self,
        gesture_inference_service: GestureInferenceService,
        frame_buffer: LatestFrameBuffer,
        *,
        input_width: int | None = None,
        input_height: int | None = None,
        process_every_nth_frame: int = 1,
        perf_log_interval_ms: int = 5000,
    ) -> None:
        super().__init__()
        self.gesture_inference_service = gesture_inference_service
        self.frame_buffer = frame_buffer
        self.input_width = input_width if input_width and input_width > 0 else None
        self.input_height = input_height if input_height and input_height > 0 else None
        self.process_every_nth_frame = max(1, int(process_every_nth_frame))
        self.perf_log_interval_ms = perf_log_interval_ms if perf_log_interval_ms > 0 else 5000
        self._running = False
        self._received_frame_counter = 0
        self._received_frames_since_log = 0
        self._processed_frames_since_log = 0
        self._skipped_frames_since_log = 0
        self._processing_total_ms = 0.0
        self._last_freshness_ms = 0
        self._perf_window_started_at = monotonic()
        self._last_input_shape: tuple[int, ...] | None = None
        self._last_inference_shape: tuple[int, ...] | None = None
        self._last_logged_resize_shapes: tuple[tuple[int, ...] | None, tuple[int, ...] | None] | None = None

    def start(self) -> None:
        if self._running:
            gesture_debug_log("thread.worker_start_skipped", worker="inference", reason="already_running")
            return

        self._running = True
        gesture_debug_log("thread.worker_started", worker="inference")
        self.workerStarted.emit()

        try:
            while self._running:
                item = self.frame_buffer.take_latest()
                if item is None:
                    self._emit_performance_log_if_due()
                    time.sleep(0.01)
                    continue

                frame, submitted_at = item
                self._received_frame_counter += 1
                self._received_frames_since_log += 1

                if self.process_every_nth_frame > 1 and ((self._received_frame_counter - 1) % self.process_every_nth_frame) != 0:
                    self._skipped_frames_since_log += 1
                    self._emit_performance_log_if_due()
                    continue

                input_shape = getattr(frame, "shape", None)
                inference_frame = self._prepare_inference_frame(frame)
                inference_shape = getattr(inference_frame, "shape", None)
                self._last_input_shape = input_shape
                self._last_inference_shape = inference_shape
                resize_shapes = (input_shape, inference_shape)
                if resize_shapes != self._last_logged_resize_shapes:
                    gesture_debug_log(
                        "inference.resize_path",
                        original_frame_size=input_shape,
                        inference_frame_size=inference_shape,
                    )
                    self._last_logged_resize_shapes = resize_shapes

                started_at = monotonic()
                try:
                    result = self.gesture_inference_service.process_frame(inference_frame)
                except Exception as exc:
                    gesture_debug_log(
                        "thread.worker_error",
                        worker="inference",
                        stage="process_frame",
                        error=f"{type(exc).__name__}: {exc}",
                    )
                    self._emit_performance_log_if_due()
                    continue

                processing_ms = (monotonic() - started_at) * 1000.0
                freshness_ms = max(0, int((monotonic() - submitted_at) * 1000.0))
                self._processed_frames_since_log += 1
                self._processing_total_ms += processing_ms
                self._last_freshness_ms = freshness_ms
                self.inferenceReady.emit(
                    InferenceUpdate(
                        result=result,
                        freshness_ms=freshness_ms,
                        processing_ms=processing_ms,
                        input_shape=input_shape,
                        inference_shape=inference_shape,
                    )
                )
                self._emit_performance_log_if_due()
        finally:
            self._running = False
            gesture_debug_log("thread.worker_finished", worker="inference")
            self.workerFinished.emit()

    def stop(self) -> None:
        gesture_debug_log("thread.worker_stop_requested", worker="inference", running=self._running)
        self._running = False
        self.frame_buffer.clear()

    def _prepare_inference_frame(self, frame: Any) -> Any:
        if self.input_width is None and self.input_height is None:
            return frame
        current_shape = getattr(frame, "shape", None)
        if not isinstance(current_shape, tuple) or len(current_shape) < 2:
            return frame
        source_height = int(current_shape[0])
        source_width = int(current_shape[1])
        target_width = self.input_width or source_width
        target_height = self.input_height or source_height
        scale = min(target_width / max(1, source_width), target_height / max(1, source_height), 1.0)
        resized_width = max(1, int(source_width * scale))
        resized_height = max(1, int(source_height * scale))
        if source_width == resized_width and source_height == resized_height:
            return frame
        try:
            return cv2.resize(frame, (resized_width, resized_height), interpolation=cv2.INTER_AREA)
        except cv2.error as exc:
            gesture_debug_log(
                "thread.worker_error",
                worker="inference",
                stage="resize",
                error=f"{type(exc).__name__}: {exc}",
                input_shape=current_shape,
                target_width=resized_width,
                target_height=resized_height,
            )
            return frame

    def _emit_performance_log_if_due(self) -> None:
        now = monotonic()
        elapsed_ms = (now - self._perf_window_started_at) * 1000.0
        if elapsed_ms < self.perf_log_interval_ms:
            return
        inference_fps = self._processed_frames_since_log / max(0.001, elapsed_ms / 1000.0)
        average_processing_ms = (
            self._processing_total_ms / self._processed_frames_since_log
            if self._processed_frames_since_log > 0
            else 0.0
        )
        dropped_frames = self.frame_buffer.take_dropped_count()
        gesture_debug_log(
            "performance.inference",
            inference_fps=f"{inference_fps:.2f}",
            average_inference_ms=f"{average_processing_ms:.2f}",
            effective_inference_fps=f"{inference_fps:.2f}",
            original_frame_size=self._last_input_shape,
            inference_frame_size=self._last_inference_shape,
            dropped_frame_count=dropped_frames,
            skipped_frame_count=self._skipped_frames_since_log,
            pending_frame_count=self.frame_buffer.pending_count(),
            latest_frame_age_ms=self.frame_buffer.pending_age_ms() or self._last_freshness_ms,
        )
        self._received_frames_since_log = 0
        self._processed_frames_since_log = 0
        self._skipped_frames_since_log = 0
        self._processing_total_ms = 0.0
        self._perf_window_started_at = now
