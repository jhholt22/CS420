from __future__ import annotations

from dataclasses import dataclass
import socket
import threading
import time
from typing import Optional

from server.core.drone.state_parser import parse_state
from server.core.util.log import log


@dataclass(slots=True)
class CommandResponse:
    raw_bytes: bytes
    decoded: str
    decode_error: str | None

    @property
    def raw_hex(self) -> str:
        return self.raw_bytes.hex()


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
        self._sdk_mode_enabled = False

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

            ok = self._enter_sdk_mode()
            if ok:
                log("[DRONE]", "SDK mode enabled", sdk_mode=True)
            else:
                log("[DRONE]", "Failed to enter SDK mode", sdk_mode=False)

            return ok
        except OSError as exc:
            log("[DRONE]", "Connect failed", error=exc)
            return False

    def close(self) -> None:
        self._state_running = False
        self._sdk_mode_enabled = False

        if self._state_thread and self._state_thread.is_alive():
            self._state_thread.join(timeout=1.0)

        if self._cmd_sock:
            self._cmd_sock.close()
        if self._state_sock:
            self._state_sock.close()

    def send_command(self, cmd: str) -> bool:
        if not self.enabled:
            return True

        if not self._sdk_mode_enabled and cmd.strip().lower() != "command":
            log("[DRONE][SDK]", "Blocked command before SDK mode", cmd=cmd, sdk_mode=self._sdk_mode_enabled)
            return False

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
        ok = self._enter_sdk_mode()
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
            "sdk_mode": self._sdk_mode_enabled,
        }

    def is_sdk_mode_enabled(self) -> bool:
        return self._sdk_mode_enabled

    def _send_raw(self, cmd: str, timeout: float | None = None) -> bool:
        original_timeout: float | None = None
        try:
            assert self._cmd_sock is not None
            original_timeout = self._cmd_sock.gettimeout()
            if timeout is not None:
                self._cmd_sock.settimeout(timeout)
            log("[DRONE][UDP]", "Command sent", cmd=cmd, timeout_s=timeout or original_timeout)
            self._cmd_sock.sendto(cmd.encode("utf-8"), self.tello_addr)
            response = self._receive_response()
            log(
                "[DRONE][UDP]",
                "Decoded response",
                cmd=cmd,
                response=response.decoded,
                decode_error=response.decode_error,
            )
            self._update_sdk_mode_state(cmd, response.decoded)
            return response.decoded.lower() == "ok"
        except socket.timeout as exc:
            self._update_sdk_mode_state(cmd, None)
            log("[DRONE]", "Command timed out", cmd=cmd, timeout_s=timeout or original_timeout, error=exc)
            return False
        except OSError as exc:
            self._update_sdk_mode_state(cmd, None)
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
                raw = data.decode("utf-8", errors="replace")
                parsed = parse_state(raw)

                with self._state_lock:
                    self._last_state = parsed
            except Exception:
                continue

    def _receive_response(self) -> CommandResponse:
        assert self._cmd_sock is not None
        data, addr = self._cmd_sock.recvfrom(1024)
        decoded, decode_error = self._decode_response_bytes(data)
        log(
            "[DRONE][UDP]",
            "Raw response received",
            peer=addr,
            raw_len=len(data),
            raw_hex=data.hex(),
        )
        return CommandResponse(raw_bytes=data, decoded=decoded.strip(), decode_error=decode_error)

    def _enter_sdk_mode(self, attempts: int = 2) -> bool:
        self._sdk_mode_enabled = False
        for attempt in range(1, attempts + 1):
            log("[DRONE][SDK]", "Entering SDK mode", attempt=attempt, max_attempts=attempts)
            if self._send_raw("command"):
                log("[DRONE][SDK]", "SDK mode success", attempt=attempt)
                return True
            log("[DRONE][SDK]", "SDK mode attempt failed", attempt=attempt)
            if attempt < attempts:
                time.sleep(0.25)
        log("[DRONE][SDK]", "SDK mode failure", attempts=attempts)
        return False

    def _update_sdk_mode_state(self, cmd: str, response: str | None) -> None:
        if cmd.strip().lower() != "command":
            return
        self._sdk_mode_enabled = bool(response and response.lower() == "ok")

    @staticmethod
    def _decode_response_bytes(data: bytes) -> tuple[str, str | None]:
        try:
            return data.decode("utf-8"), None
        except UnicodeDecodeError as exc:
            return data.decode("utf-8", errors="backslashreplace"), f"{type(exc).__name__}: {exc}"

    def _timeout_for_command(self, cmd: str) -> float:
        return self.motion_cmd_timeout if self._is_motion_command(cmd) else self.cmd_timeout

    @staticmethod
    def _is_motion_command(cmd: str) -> bool:
        base = cmd.strip().split(" ", 1)[0].lower()
        return base in {"forward", "back", "left", "right", "up", "down", "cw", "ccw", "rc"}
