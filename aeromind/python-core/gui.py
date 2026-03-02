import cv2

class GUI:
    def __init__(self, window_name: str = "AeroMind"):
        self.window_name = window_name
        self.gesture_true = ""   # you can label trials manually
        self.running = True

    def draw(self, frame, pred, decision, sim_state=None):
        # overlay text
        cv2.putText(frame, f"pred: {pred.gesture} ({pred.confidence:.2f})", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.putText(frame, f"stable_ms: {decision.reason}", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cmd_txt = decision.command if decision.allowed else "none"
        cv2.putText(frame, f"cmd: {cmd_txt}", (10, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        if self.gesture_true:
            cv2.putText(frame, f"label: {self.gesture_true}", (10, 120),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

        if sim_state is not None:
            cv2.putText(frame, f"sim: {sim_state}", (10, 150),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

        cv2.imshow(self.window_name, frame)

    def handle_keys(self):
        k = cv2.waitKey(1) & 0xFF

        # quit
        if k == ord("q"):
            self.running = False

        # quick label keys (you can change these)
        if k == ord("1"): self.gesture_true = "takeoff"
        if k == ord("2"): self.gesture_true = "land"
        if k == ord("3"): self.gesture_true = "forward"
        if k == ord("4"): self.gesture_true = "backward"
        if k == ord("5"): self.gesture_true = "rotate_left"
        if k == ord("0"): self.gesture_true = "none"
        if k == ord("x"): self.gesture_true = "emergency_stop"

        return self.running

    def close(self):
        cv2.destroyAllWindows()
