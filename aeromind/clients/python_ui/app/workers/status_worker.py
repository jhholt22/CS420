from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal

from app.config import STATUS_REFRESH_MS
from app.services.api_client import ApiClient, ApiClientError


class StatusWorker(QObject):
    statusUpdated = Signal(dict, object)
    statusError = Signal(str)

    def __init__(self, api_client: ApiClient, refresh_ms: int = STATUS_REFRESH_MS) -> None:
        super().__init__()
        self.api_client = api_client
        self.refresh_ms = refresh_ms
        self._timer = QTimer(self)
        self._timer.setInterval(self.refresh_ms)
        self._timer.timeout.connect(self.poll_once)

    def start(self) -> None:
        if not self._timer.isActive():
            self._timer.start()
        self.poll_once()

    def stop(self) -> None:
        if self._timer.isActive():
            self._timer.stop()

    def poll_once(self) -> None:
        try:
            status_data = self.api_client.get_status()
            state_data = None
            if status_data.get("running"):
                state_data = self.api_client.get_state()
            self.statusUpdated.emit(status_data, state_data)
        except ApiClientError as exc:
            self.statusError.emit(str(exc))
