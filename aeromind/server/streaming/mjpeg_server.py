from __future__ import annotations

import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import cv2

from server.core.util.log import log


class MjpegServer:
    def __init__(
        self,
        frame_bus,
        host: str = "127.0.0.1",
        port: int = 8080,
        fps: int = 12,
        jpeg_quality: int = 80,
    ):
        self.frame_bus = frame_bus
        self.host = host
        self.port = port
        self.fps = fps
        self.jpeg_quality = jpeg_quality

        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return

        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path not in ("/video", "/stream/video"):
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b"Not Found")
                    return

                self.send_response(200)
                self.send_header("Age", "0")
                self.send_header("Cache-Control", "no-cache, private")
                self.send_header("Pragma", "no-cache")
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.end_headers()

                frame_interval = 1.0 / max(1, outer.fps)

                try:
                    while outer._running:
                        frame, _ = outer.frame_bus.get_latest()
                        if frame is None:
                            time.sleep(frame_interval)
                            continue

                        ok, jpg = cv2.imencode(
                            ".jpg",
                            frame,
                            [int(cv2.IMWRITE_JPEG_QUALITY), outer.jpeg_quality],
                        )
                        if not ok:
                            time.sleep(frame_interval)
                            continue

                        payload = jpg.tobytes()

                        self.wfile.write(b"--frame\r\n")
                        self.wfile.write(b"Content-Type: image/jpeg\r\n")
                        self.wfile.write(f"Content-Length: {len(payload)}\r\n\r\n".encode("utf-8"))
                        self.wfile.write(payload)
                        self.wfile.write(b"\r\n")

                        time.sleep(frame_interval)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                except Exception as exc:
                    log("[MJPEG]", "Client stream error", error=exc)

            def log_message(self, format: str, *args: Any) -> None:
                # silence default HTTP server logs
                return

        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self._running = True
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

        log("[MJPEG]", "Server started", host=self.host, port=self.port)

    def stop(self) -> None:
        if not self._running:
            return

        self._running = False

        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

        log("[MJPEG]", "Server stopped")