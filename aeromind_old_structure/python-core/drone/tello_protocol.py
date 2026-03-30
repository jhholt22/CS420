import socket
import threading
import time
from dataclasses import dataclass


@dataclass
class CommandResult:
    ok: bool
    command: str
    response: str
    error_type: str
    rtt_ms: int


class TelloProtocol:
    def __init__(
        self,
        tello_ip: str,
        tello_cmd_port: int,
        local_cmd_port: int,
        timeout_s: float,
    ):
        self.tello_ip = tello_ip
        self.tello_cmd_port = tello_cmd_port
        self.local_cmd_port = local_cmd_port
        self.timeout_s = timeout_s

        self._sock: socket.socket | None = None
        self._lock = threading.Lock()

        self.total = 0
        self.ok_count = 0
        self.error_count = 0
        self.timeout_count = 0
        self.last_command = ""
        self.last_response = ""
        self.last_rtt_ms = 0

    @property
    def is_open(self) -> bool:
        return self._sock is not None

    def open(self):
        self.close()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", self.local_cmd_port))
        sock.settimeout(self.timeout_s)
        self._sock = sock

    def close(self):
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    def send(self, cmd: str, expect_ok: bool = True, retries: int = 1) -> CommandResult:
        if not self._sock:
            return CommandResult(False, cmd, "", "socket_closed", 0)

        last_result = CommandResult(False, cmd, "", "unknown", 0)
        tries = max(1, retries)

        with self._lock:
            for _ in range(tries):
                t0 = time.monotonic()
                self.total += 1
                self.last_command = cmd
                try:
                    self._sock.sendto(cmd.encode("utf-8"), (self.tello_ip, self.tello_cmd_port))
                    data, _ = self._sock.recvfrom(1024)
                    resp = data.decode("utf-8", errors="ignore").strip()
                    rtt = int((time.monotonic() - t0) * 1000)
                    self.last_response = resp
                    self.last_rtt_ms = rtt

                    low = resp.lower()
                    if expect_ok and low != "ok":
                        self.error_count += 1
                        last_result = CommandResult(False, cmd, resp, "error_response", rtt)
                    else:
                        self.ok_count += 1
                        return CommandResult(True, cmd, resp, "none", rtt)

                except socket.timeout:
                    rtt = int((time.monotonic() - t0) * 1000)
                    self.timeout_count += 1
                    self.last_response = "timeout"
                    self.last_rtt_ms = rtt
                    last_result = CommandResult(False, cmd, "timeout", "timeout", rtt)
                except Exception as exc:
                    rtt = int((time.monotonic() - t0) * 1000)
                    self.error_count += 1
                    self.last_response = str(exc)
                    self.last_rtt_ms = rtt
                    last_result = CommandResult(False, cmd, str(exc), "socket_error", rtt)

                time.sleep(0.12)

        return last_result
