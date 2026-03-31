from __future__ import annotations

import socket
import threading
import time
from typing import Optional

from server.core.drone.state_parser import parse_state
from server.core.util.log import log


class DroneInterface:
    def __init__(
        self,
        enabled: bool,
        tello_ip: str,
        cmd_port: int,
        state_port: int,
        local_cmd_port: int,
        cmd_timeout: float,
        motion_cmd_timeout: float,
    ):
        self.enabled = enabled
        self.tello_addr = (tello_ip, cmd_port)
        self.state_port = state_port
        self.local_cmd_port = local_cmd_port
        self.cmd_timeout = cmd_timeout
        self.motion_cmd_timeout = motion_cmd_timeout

        self._cmd_sock: Optional[socket.socket] = None
        self._state_sock: Optional[socket.socket] = None

        self._state_thread: Optional[threading.Thread] = None
        self._state_running = False
        self._state_lock = threading.Lock()
        self._last_state: dict = {}

        self.is_flying = False

    def connect(self) -> bool:
        if not self.enabled:
            return True

        try:
            self._cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._cmd_sock.bind(("", self.local_cmd_port))
            self._cmd_sock.settimeout(self.cmd_timeout)

            self._state_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._state_sock.bind(("", self.state_port))

            self._state_running = True
            self._state_thread = threading.Thread(target=self._state_loop, daemon=True)
            self._state_thread.start()

            ok = self._send_raw("command")
            if ok:
                log("[DRONE]", "SDK mode enabled")
            else:
                log("[DRONE]", "Failed to enter SDK mode")

            return ok
        except Exception as exc:
            log("[DRONE]", "Connect failed", error=exc)
            return False

    def close(self) -> None:
        self._state_running = False

        if self._state_thread and self._state_thread.is_alive():
            self._state_thread.join(timeout=1.0)

        if self._cmd_sock:
            self._cmd_sock.close()
        if self._state_sock:
            self._state_sock.close()

    def send_command(self, cmd: str) -> bool:
        if not self.enabled:
            return True

        ok = self._send_raw(cmd, timeout=self._timeout_for_command(cmd))

        if ok:
            if cmd == "takeoff":
                self.is_flying = True
            elif cmd in ("land", "emergency"):
                self.is_flying = False

        return ok

    def recover(self) -> bool:
        if not self.enabled:
            return True

        log("[DRONE]", "Recovery sequence")
        self._send_raw("emergency")
        time.sleep(0.2)
        ok = self._send_raw("command")
        return ok

    def poll_state(self) -> dict:
        with self._state_lock:
            return dict(self._last_state)

    def diagnostics(self) -> dict:
        state = self.poll_state()
        return {
            "battery_pct": state.get("battery_pct"),
            "height_cm": state.get("height_cm"),
            "flight_state": state.get("flight_state"),
            "connected": self.enabled,
        }

    def _send_raw(self, cmd: str, timeout: float | None = None) -> bool:
        try:
            assert self._cmd_sock is not None
            original_timeout = self._cmd_sock.gettimeout()
            if timeout is not None:
                self._cmd_sock.settimeout(timeout)
            self._cmd_sock.sendto(cmd.encode("utf-8"), self.tello_addr)
            data, _ = self._cmd_sock.recvfrom(1024)
            response = data.decode("utf-8").strip()
            return response == "ok"
        except Exception as exc:
            log("[DRONE]", "Command failed", cmd=cmd, error=exc)
            return False
        finally:
            if self._cmd_sock is not None and timeout is not None:
                self._cmd_sock.settimeout(original_timeout)

    def _state_loop(self) -> None:
        assert self._state_sock is not None

        while self._state_running:
            try:
                data, _ = self._state_sock.recvfrom(2048)
                raw = data.decode("utf-8")
                parsed = parse_state(raw)

                with self._state_lock:
                    self._last_state = parsed
            except Exception:
                continue

    def _timeout_for_command(self, cmd: str) -> float:
        return self.motion_cmd_timeout if self._is_motion_command(cmd) else self.cmd_timeout

    @staticmethod
    def _is_motion_command(cmd: str) -> bool:
        base = cmd.strip().split(" ", 1)[0].lower()
        return base in {"forward", "back", "left", "right", "up", "down", "cw", "ccw", "rc"}
