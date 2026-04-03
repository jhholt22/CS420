from __future__ import annotations

import time

from PySide6.QtCore import QObject, Signal

from app.config import STATUS_REFRESH_MS
from app.services.api_client import ApiClient, ApiClientError
from app.utils.logging_utils import gesture_debug_log


class StatusWorker(QObject):
    statusUpdated = Signal(dict, object, dict)
    statusError = Signal(str)
    workerStarted = Signal()
    workerFinished = Signal()

    def __init__(self, api_client: ApiClient, refresh_ms: int = STATUS_REFRESH_MS) -> None:
        super().__init__()
        self.api_client = api_client
        self.refresh_ms = refresh_ms if isinstance(refresh_ms, int) and refresh_ms > 0 else STATUS_REFRESH_MS
        self._running = False
        self._last_error_text: str | None = None

    def start(self) -> None:
        if self._running:
            gesture_debug_log("thread.worker_start_skipped", worker="status", reason="already_running")
            return

        self._running = True
        gesture_debug_log("thread.worker_started", worker="status")
        self.workerStarted.emit()
        try:
            while self._running:
                try:
                    status_data = self.api_client.get_status()
                    if not self._running:
                        break
                    state_data = self.api_client.get_state()
                    if not self._running:
                        break
                    diag_data = self.api_client.get_diag()
                    if not self._running:
                        break
                    self._last_error_text = None
                    self.statusUpdated.emit(status_data, state_data, diag_data)
                except ApiClientError as exc:
                    self._emit_error(str(exc))
                except RuntimeError as exc:
                    self._emit_error(f"Status polling failed: {exc}")

                if not self._running:
                    break
                self._sleep_interval()
        finally:
            self._running = False
            gesture_debug_log("thread.worker_finished", worker="status")
            self.workerFinished.emit()

    def stop(self) -> None:
        gesture_debug_log("thread.worker_stop_requested", worker="status", running=self._running)
        self._running = False

    def _emit_error(self, error_text: str) -> None:
        if error_text != self._last_error_text:
            self._last_error_text = error_text
            self.statusError.emit(error_text)

    def _sleep_interval(self) -> None:
        remaining = self.refresh_ms / 1000.0
        while self._running and remaining > 0:
            step = min(0.1, remaining)
            time.sleep(step)
            remaining -= step
