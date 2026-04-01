from __future__ import annotations

from typing import Any

import requests


class ApiClientError(RuntimeError):
    pass


class ApiClient:
    def __init__(self, base_url: str, timeout: float = 2.0) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self.session = requests.Session()

    def start_controller(self, mode: str) -> dict[str, Any]:
        return self._request("POST", "/start", json={"mode": mode})

    def stop_controller(self) -> dict[str, Any]:
        return self._request("POST", "/stop")

    def get_status(self) -> dict[str, Any]:
        return self._request("GET", "/status")

    def get_state(self) -> dict[str, Any]:
        return self._request("GET", "/state")

    def send_command(self, command: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"command": command}
        if args:
            payload["args"] = args
        return self._request("POST", "/command", json=payload)

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = self.session.request(
                method,
                f"{self.base_url}{path}",
                timeout=kwargs.pop("timeout", self.timeout),
                **kwargs,
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ApiClientError(f"Unexpected response payload for {path}")
            return data
        except requests.RequestException as exc:
            raise ApiClientError(f"{method} {path} failed: {exc}") from exc
        except ValueError as exc:
            raise ApiClientError(f"{method} {path} returned invalid JSON") from exc
