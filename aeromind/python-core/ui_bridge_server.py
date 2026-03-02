import json
import socket
import threading
from queue import Queue, Empty


class UiBridgeServer:
    """
    TCP NDJSON server on localhost for JavaFX <-> Python communication.
    - Java connects as a client.
    - Java sends one JSON per line.
    - Python can send telemetry snapshots back (one JSON per line).
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 7070):
        self.host = host
        self.port = port

        self._srv: socket.socket | None = None
        self._client: socket.socket | None = None
        self._client_lock = threading.Lock()

        self._running = False
        self._thread: threading.Thread | None = None

        self._inbox: Queue[dict] = Queue()

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
                except:
                    pass
                self._client = None

        if self._srv:
            try:
                self._srv.close()
            except:
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
            if not self._client:
                return
            try:
                self._client.sendall(data)
            except:
                try:
                    self._client.close()
                except:
                    pass
                self._client = None

    # ----------------- internals -----------------
    def _run(self):
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind((self.host, self.port))
        self._srv.listen(1)
        self._srv.settimeout(0.5)

        buf = b""

        while self._running:
            # accept client if none
            if not self._client:
                try:
                    client, _addr = self._srv.accept()
                    client.settimeout(0.5)
                    with self._client_lock:
                        self._client = client
                    buf = b""
                    print(f"[UI] Java connected on {self.host}:{self.port}")
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
                    continue

                buf += chunk

                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not line.strip():
                        continue
                    try:
                        msg = json.loads(line.decode("utf-8"))
                        self._inbox.put(msg)
                    except:
                        continue

            except socket.timeout:
                continue
            except OSError:
                with self._client_lock:
                    self._client = None
                continue