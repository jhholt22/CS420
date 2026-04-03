from __future__ import annotations

from typing import Any

import requests
from app.utils.logging_utils import gesture_debug_log


class ApiClientError(RuntimeError):
    pass


class ApiClient:
    def __init__(self, base_url: str, timeout: float = 2.0) -> None:
        self.base_url = base_url.rstrip("/")
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

    def get_diag(self) -> dict[str, Any]:
        response = self._request("GET", "/diag")
        diag = response.get("diag")
        if not isinstance(diag, dict):
            raise ApiClientError("GET /diag returned unexpected data")
        return diag

    def send_command(self, command: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"command": command}
        if args:
            payload["args"] = args
        gesture_debug_log(
            "api.send_command",
            raw_gesture="-",
            stable_gesture="-",
            confidence="-",
            resolved_command=command,
            queue_state="dispatch_attempt",
            detector_available="-",
        )
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
        except requests.Timeout as exc:
            raise ApiClientError(f"{method} {path} timed out") from exc
        except requests.ConnectionError as exc:
            raise ApiClientError(f"{method} {path} unavailable") from exc
        except requests.HTTPError as exc:
            raise ApiClientError(self._format_http_error(method, path, exc.response)) from exc
        except requests.RequestException as exc:
            raise ApiClientError(f"{method} {path} request failed") from exc
        except ValueError as exc:
            raise ApiClientError(f"{method} {path} returned invalid JSON") from exc

        if not isinstance(data, dict):
            raise ApiClientError(f"{method} {path} returned unexpected data")
        if method == "POST" and path == "/command":
            gesture_debug_log(
                "api.command_response",
                raw_gesture="-",
                stable_gesture="-",
                confidence="-",
                resolved_command=str(data.get("command", "-")),
                queue_state="dispatch_ok",
                detector_available="-",
            )
        return data

    def _format_http_error(self, method: str, path: str, response: requests.Response | None) -> str:
        if response is None:
            return f"{method} {path} returned HTTP error"

        status_code = response.status_code
        if status_code == 400:
            detail = self._extract_error_detail(response)
            if detail:
                return f"{method} {path} bad request: {detail}"
            return f"{method} {path} bad request"

        return f"{method} {path} returned HTTP {status_code}"

    @staticmethod
    def _extract_error_detail(response: requests.Response) -> str | None:
        try:
            payload = response.json()
        except ValueError:
            payload = None

        if isinstance(payload, dict):
            for key in ("error", "message", "detail"):
                value = payload.get(key)
                if value is not None:
                    text = str(value).strip()
                    if text:
                        return text

        text = response.text.strip()
        if text:
            compact = " ".join(text.split())
            return compact[:120]
        return None
