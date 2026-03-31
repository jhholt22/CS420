from __future__ import annotations


class Simulator:
    def __init__(self):
        self.x = 0
        self.y = 0
        self.z = 0
        self.yaw = 0
        self.flying = False

    def apply(self, cmd: str) -> None:
        if cmd == "takeoff":
            self.flying = True
        elif cmd == "land":
            self.flying = False
        elif cmd.startswith("forward") and self.flying:
            self.y += 1
        elif cmd.startswith("back") and self.flying:
            self.y -= 1
        elif cmd.startswith("ccw") and self.flying:
            self.yaw -= 10
        elif cmd.startswith("cw") and self.flying:
            self.yaw += 10
        elif cmd.startswith("rc ") and self.flying:
            parts = cmd.split()
            if len(parts) == 5:
                left_right = int(parts[1])
                forward_back = int(parts[2])
                up_down = int(parts[3])
                yaw = int(parts[4])
                self.x += left_right
                self.y += forward_back
                self.z += up_down
                self.yaw += yaw
        elif cmd == "emergency":
            self.flying = False

    def snapshot(self) -> dict:
        return {
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "yaw": self.yaw,
            "flying": self.flying,
        }
