import threading
import time

import cv2
from flask import Flask, Response
from werkzeug.serving import make_server

from util.log import log


class MjpegServer:
    def __init__(self, frame_bus, host: str = "127.0.0.1", port: int = 8080, fps: int = 12, jpeg_quality: int = 80):
        self.frame_bus = frame_bus
        self.host = host
        self.port = port
        self.fps = fps
        self.jpeg_quality = jpeg_quality

        self._app = Flask("aeromind-mjpeg")
        self._server = None
        self._thread = None
        self._running = False

        self._setup_routes()

    def _setup_routes(self):
        @self._app.get("/video")
        def video():
            return Response(self._stream(), mimetype="multipart/x-mixed-replace; boundary=frame")

        @self._app.get("/health")
        def health():
            return {"ok": True}

    def start(self):
        if self._running:
            return
        self._running = True

        self._server = make_server(self.host, self.port, self._app, threaded=True)
        self._thread = threading.Thread(target=self._server.serve_forever, name="mjpeg-server", daemon=True)
        self._thread.start()
        log("[VIDEO]", "MJPEG server started", url=f"http://{self.host}:{self.port}/video")

    def stop(self):
        self._running = False
        if self._server:
            try:
                self._server.shutdown()
            except Exception:
                pass
            self._server = None

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._thread = None
        log("[VIDEO]", "MJPEG server stopped")

    def _stream(self):
        boundary = b"--frame\r\n"
        header = b"Content-Type: image/jpeg\r\n\r\n"
        last_seq = -1
        period = 1.0 / max(1, self.fps)

        while self._running:
            frame, _ts, seq = self.frame_bus.latest()
            if frame is None or seq == last_seq:
                time.sleep(0.02)
                continue

            ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), int(self.jpeg_quality)])
            if not ok:
                time.sleep(period)
                continue

            last_seq = seq
            yield boundary + header + buf.tobytes() + b"\r\n"
            time.sleep(period)
