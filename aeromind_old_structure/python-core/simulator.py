class Simulator:
    def __init__(self):
        self.x = 0
        self.y = 0
        self.yaw = 0
        self.flying = False

    def apply(self, cmd: str):
        # minimal fake physics
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
        elif cmd == "emergency":
            self.flying = False

    def snapshot(self):
        return {"x": self.x, "y": self.y, "yaw": self.yaw, "flying": self.flying}
