from __future__ import annotations

import socket
from typing import Optional


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

        self._sock.sendto(cmd.encode("utf-8"), self.tello_addr)
        data, _ = self._sock.recvfrom(1024)
        return data.decode("utf-8").strip()