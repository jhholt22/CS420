import cv2
import time


class TelloVideoSource:
    """
    OpenCV reader for Tello UDP video 11111
    lifecycle:
      video = TelloVideoSource(drone)
      video.start()  # after drone.connect()
      ok, frame = video.read()
      video.release()
    """

    def __init__(self, drone_interface, *, warmup_s: float = 0.8):
        self.drone = drone_interface
        self.warmup_s = warmup_s
        self.cap = None
        self._started = False

    def start(self) -> bool:
        if self._started:
            return True

        if not getattr(self.drone, "enabled", False) or not getattr(self.drone, "cmd_sock", None):
            print("[Video] Drone not connected yet")
            return False

        # start clean
        try:
            self.drone.send_command("streamoff")
        except:
            pass
        if not self.drone.send_command("streamon"):
            print("[Video] streamon failed")
            return False

        def open_cap():
            cap = cv2.VideoCapture("udp://0.0.0.0:11111", cv2.CAP_FFMPEG)
            try:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # may or may not be supported
            except:
                pass
            return cap

        self.cap = open_cap()
        time.sleep(self.warmup_s)

        # flush until we get a real frame
        ok_frame = False
        for _ in range(120):  # ~6s at 20Hz polling
            ok, frame = self.cap.read()
            if ok and frame is not None and frame.size > 0:
                ok_frame = True
                break
            time.sleep(0.05)

        # if still bad, reopen ONCE (often fixes PPS spam)
        if not ok_frame:
            try:
                self.cap.release()
            except:
                pass
            self.cap = open_cap()
            time.sleep(0.5)

            for _ in range(120):
                ok, frame = self.cap.read()
                if ok and frame is not None and frame.size > 0:
                    ok_frame = True
                    break
                time.sleep(0.05)

        if ok_frame:
            self._started = True
            print("[Video] Tello stream ready")
            return True

        print("[Video] No decodable frames from Tello stream")
        return False

    def read(self):
        if not self.cap:
            return False, None
        return self.cap.read()

    def release(self):
        if self.cap:
            try:
                self.cap.release()
            except:
                pass
            self.cap = None

        if self._started and getattr(self.drone, "enabled", False):
            try:
                self.drone.send_command("streamoff")
            except:
                pass
        self._started = False