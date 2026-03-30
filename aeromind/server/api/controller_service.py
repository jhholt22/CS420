from __future__ import annotations

import threading

from server.core.app.app_controller import AppController
from server.core.app.runtime_config import RuntimeConfig
from server.core.util.log import log


class ControllerService:
    def __init__(self):
        self._lock = threading.RLock()
        self._controller: AppController | None = None
        self._thread: threading.Thread | None = None
        self._mode: str | None = None

    def start(self, mode: str) -> dict:
        normalized_mode = mode.strip().lower()
        if normalized_mode not in {"sim", "drone"}:
            raise ValueError("mode must be 'sim' or 'drone'")

        with self._lock:
            if self._is_controller_running_locked():
                return {
                    "started": False,
    "stopped": False,
    "already_running": True,
    "was_running": False,
    "mode": self._mode,
                }

            controller = AppController(
                use_drone=normalized_mode == "drone",
                cfg=RuntimeConfig(),
            )
            thread = threading.Thread(
                target=self._run_controller,
                args=(controller, normalized_mode),
                name=f"aeromind-controller-{normalized_mode}",
                daemon=True,
            )

            self._controller = controller
            self._thread = thread
            self._mode = normalized_mode

            thread.start()
            log("[API]", "Controller start requested", mode=normalized_mode)

            return {
                "started": True,
                "already_running": False,
                "mode": normalized_mode,
            }

    def stop(self) -> dict:
        with self._lock:
            controller = self._controller
            thread = self._thread
            mode = self._mode
            running = self._is_controller_running_locked()

        if not running or controller is None:
            return {
                "stopped": False,
                "was_running": False,
                "mode": mode,
            }

        log("[API]", "Controller stop requested", mode=mode)
        controller.stop()

        if thread and thread.is_alive():
            thread.join(timeout=5.0)

        if thread and thread.is_alive():
            log("[API]", "Controller thread did not exit before timeout", mode=mode)
            return {
                "stopped": False,
                "was_running": True,
                "mode": mode,
            }

        with self._lock:
            if self._thread is thread:
                self._controller = None
                self._thread = None
                self._mode = None

        return {
            "stopped": True,
            "was_running": True,
            "mode": mode,
        }

    def get_state(self) -> dict:
        controller = self._get_running_controller()
        return controller.get_api_state()

    def get_diag(self) -> dict:
        controller = self._get_running_controller()
        return controller.collect_diag()

    def status(self) -> dict:
        with self._lock:
            if self._controller is not None:
                return self._controller.get_api_status()
            return {
                "running": self._is_controller_running_locked(),
                "mode": self._mode,
            }

    def _run_controller(self, controller: AppController, mode: str) -> None:
        try:
            controller.run()
        except Exception as exc:
            log("[API]", "Controller thread failed", mode=mode, error=exc)
            raise
        finally:
            with self._lock:
                if self._controller is controller:
                    self._controller = None
                    self._thread = None
                    self._mode = None
            log("[API]", "Controller thread exited", mode=mode)

    def _get_running_controller(self) -> AppController:
        with self._lock:
            if not self._is_controller_running_locked() or self._controller is None:
                raise RuntimeError("controller is not running")
            return self._controller

    def _is_controller_running_locked(self) -> bool:
        return bool(self._thread and self._thread.is_alive())