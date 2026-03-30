import json
import socket
import threading
from queue import Empty, Queue

from util.log import log


class UiBridgeServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 7070):
        self.host = host
        self.port = port

        self._srv = None
        self._client = None
        self._client_lock = threading.Lock()

        self._inbox: Queue[dict] = Queue()

        self._running = False
        self._thread = None

    @property
    def has_client(self) -> bool:
        with self._client_lock:
            return self._client is not None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, name="ui-bridge", daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        with self._client_lock:
            if self._client:
                try:
                    self._client.close()
                except Exception:
                    pass
                self._client = None

        if self._srv:
            try:
                self._srv.close()
            except Exception:
                pass
            self._srv = None

    def poll(self, max_items: int = 50) -> list[dict]:
        out = []
        for _ in range(max_items):
            try:
                out.append(self._inbox.get_nowait())
            except Empty:
                break
        return out

    def send(self, msg: dict):
        data = (json.dumps(msg) + "\n").encode("utf-8")
        with self._client_lock:
            c = self._client

        if not c:
            # heartbeat-safe: drop silently if no client
            return

        try:
            c.sendall(data)
        except Exception:
            with self._client_lock:
                try:
                    if self._client:
                        self._client.close()
                except Exception:
                    pass
                self._client = None
            log("[UI]", "Client disconnected while sending")

    def _run(self):
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind((self.host, self.port))
        self._srv.listen(1)
        self._srv.settimeout(0.5)

        buf = b""

        while self._running:
            if not self.has_client:
                try:
                    c, addr = self._srv.accept()
                    c.settimeout(0.5)
                    with self._client_lock:
                        if self._client:
                            try:
                                self._client.close()
                            except Exception:
                                pass
                        self._client = c
                    buf = b""
                    log("[UI]", "Java connected", addr=addr)
                except socket.timeout:
                    continue
                except OSError:
                    break

            with self._client_lock:
                c = self._client
            if not c:
                continue

            try:
                chunk = c.recv(4096)
                if not chunk:
                    with self._client_lock:
                        self._client = None
                    log("[UI]", "Java disconnected")
                    continue

                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not line.strip():
                        continue
                    try:
                        msg = json.loads(line.decode("utf-8"))
                        self._inbox.put(msg)
                    except Exception:
                        continue

            except socket.timeout:
                continue
            except OSError:
                with self._client_lock:
                    self._client = None
                continue
