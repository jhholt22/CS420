import threading
import time
from typing import Optional

import cv2

# Flask is simplest + stable. Install if needed:
# pip install flask
from flask import Flask, Response

class MjpegServer:
    """
    MJPEG server that streams the latest frame pushed by your main loop.
    - main loop calls server.update(frame)
    - /video streams multipart/x-mixed-replace
    - start()/stop() are clean (no stuck threads)
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8080, fps: int = 12, jpeg_quality: int = 80):
        self.host = host
        self.port = port
        self.fps = fps
        self.jpeg_quality = jpeg_quality

        self._app = Flask("aeromind-mjpeg")
        self._srv = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._latest_jpg: Optional[bytes] = None
        self._frame_seq = 0

        self._setup_routes()

    def _setup_routes(self):
        @self._app.get("/video")
        def video():
            return Response(self._stream(),
                           mimetype="multipart/x-mixed-replace; boundary=frame")

        @self._app.get("/health")
        def health():
            return {"ok": True}

    def start(self):
        if self._running:
            return
        self._running = True

        # Use Werkzeug server so we can shutdown cleanly
        from werkzeug.serving import make_server
        self._srv = make_server(self.host, self.port, self._app, threaded=True)
        self._thread = threading.Thread(target=self._srv.serve_forever, name="mjpeg-server", daemon=True)
        self._thread.start()
        print(f"[MJPEG] Serving on http://{self.host}:{self.port}/video")

    def stop(self):
        self._running = False
        with self._cond:
            self._cond.notify_all()

        if self._srv:
            try:
                self._srv.shutdown()
            except:
                pass
            self._srv = None

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._thread = None
        print("[MJPEG] Stopped")

    def update(self, frame):
        """
        Push latest frame from main loop. Keep it fast:
        - resize optional before calling update
        - encode to JPEG once here
        """
        if frame is None:
            return

        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), int(self.jpeg_quality)])
        if not ok:
            return

        jpg = buf.tobytes()
        with self._cond:
            self._latest_jpg = jpg
            self._frame_seq += 1
            self._cond.notify_all()

    def _stream(self):
        boundary = b"--frame\r\n"
        header = b"Content-Type: image/jpeg\r\n\r\n"

        last_seq = -1
        period = 1.0 / max(1, self.fps)

        while self._running:
            with self._cond:
                # wait for a new frame or timeout so client stays alive
                self._cond.wait(timeout=1.0)
                seq = self._frame_seq
                jpg = self._latest_jpg

            if jpg is None or seq == last_seq:
                continue

            last_seq = seq

            yield boundary + header + jpg + b"\r\n"
            time.sleep(period)