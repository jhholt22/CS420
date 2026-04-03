from __future__ import annotations

import socket
from typing import Optional

from server.core.util.log import log


class TelloProtocol:
    def __init__(
        self,
        tello_ip: str,
        tello_cmd_port: int,
        local_cmd_port: int,
        timeout_s: float,
    ):
        self.tello_addr = (tello_ip, tello_cmd_port)
        self.local_cmd_port = local_cmd_port
        self.timeout_s = timeout_s
        self._sock: Optional[socket.socket] = None

    def open(self) -> None:
        if self._sock is not None:
            return

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("", self.local_cmd_port))
        sock.settimeout(self.timeout_s)
        self._sock = sock

    def close(self) -> None:
        if self._sock is not None:
            self._sock.close()
            self._sock = None

    def send(self, cmd: str) -> str:
        if self._sock is None:
            raise RuntimeError("TelloProtocol socket is not open")

        log("[TELLO][UDP]", "Command sent", cmd=cmd, timeout_s=self._sock.gettimeout())
        self._sock.sendto(cmd.encode("utf-8"), self.tello_addr)
        data, _ = self._sock.recvfrom(1024)
        decoded, decode_error = self._decode_response_bytes(data)
        log(
            "[TELLO][UDP]",
            "Raw response received",
            cmd=cmd,
            raw_len=len(data),
            raw_hex=data.hex(),
        )
        log(
            "[TELLO][UDP]",
            "Decoded response",
            cmd=cmd,
            response=decoded.strip(),
            decode_error=decode_error,
        )
        return decoded.strip()

    @staticmethod
    def _decode_response_bytes(data: bytes) -> tuple[str, str | None]:
        try:
            return data.decode("utf-8"), None
        except UnicodeDecodeError as exc:
            return data.decode("utf-8", errors="backslashreplace"), f"{type(exc).__name__}: {exc}"
