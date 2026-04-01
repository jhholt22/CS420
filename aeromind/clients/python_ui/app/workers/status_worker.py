from __future__ import annotations

import time

from PySide6.QtCore import QObject, Signal

from app.config import STATUS_REFRESH_MS
from app.services.api_client import ApiClient, ApiClientError


class StatusWorker(QObject):
    statusUpdated = Signal(dict, object)
    statusError = Signal(str)

    def __init__(self, api_client: ApiClient, refresh_ms: int = STATUS_REFRESH_MS) -> None:
        super().__init__()
        self.api_client = api_client
        self.refresh_ms = refresh_ms if isinstance(refresh_ms, int) and refresh_ms > 0 else STATUS_REFRESH_MS
        self._running = False
        self._last_error_text: str | None = None

    def start(self) -> None:
        if self._running:
            return

        self._running = True
        while self._running:
            try:
                status_data = self.api_client.get_status()
                if not self._running:
                    break
                state_data = self.api_client.get_state()
                if not self._running:
                    break
                self._last_error_text = None
                self.statusUpdated.emit(status_data, state_data)
            except ApiClientError as exc:
                self._emit_error(str(exc))
            except Exception as exc:
                self._emit_error(f"Status polling failed: {exc}")

            if not self._running:
                break
            self._sleep_interval()

    def stop(self) -> None:
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
