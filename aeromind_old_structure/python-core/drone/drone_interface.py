import socket
import threading
import time
from dataclasses import dataclass

from drone.state_parser import StateParser
from drone.tello_protocol import CommandResult, TelloProtocol
from util.log import log


@dataclass
class DroneStats:
    cmd_total: int = 0
    cmd_ok: int = 0
    cmd_error: int = 0
    cmd_timeout: int = 0


class DroneInterface:
    def __init__(
        self,
        enabled: bool = False,
        *,
        tello_ip: str = "192.168.10.1",
        cmd_port: int = 8889,
        state_port: int = 8890,
        local_cmd_port: int = 9000,
        cmd_timeout: float = 2.5,
    ):
        self.enabled = enabled
        self.tello_ip = tello_ip
        self.cmd_port = cmd_port
        self.state_port = state_port

        self.protocol = TelloProtocol(
            tello_ip=tello_ip,
            tello_cmd_port=cmd_port,
            local_cmd_port=local_cmd_port,
            timeout_s=cmd_timeout,
        )

        self.state_sock: socket.socket | None = None
        self._state_thread: threading.Thread | None = None
        self._state_running = False
        self._state_lock = threading.Lock()

        self.state = {
            "battery_pct": None,
            "height_cm": None,
            "flight_state": "unknown",
        }

        self.is_flying = False
        self._consecutive_timeouts = 0
        self._stats = DroneStats()

    def connect(self) -> bool:
        if not self.enabled:
            log("[DRONE]", "SIM mode active")
            return True

        self.close()

        try:
            self.protocol.open()

            self.state_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.state_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.state_sock.bind(("0.0.0.0", self.state_port))
            self.state_sock.settimeout(0.2)

            cmd = self.protocol.send("command", expect_ok=True, retries=5)
            self._track_result(cmd)
            if not cmd.ok:
                raise RuntimeError(f"SDK mode failed: {cmd.response}")

            self._state_running = True
            self._state_thread = threading.Thread(target=self._state_loop, name="tello-state", daemon=False)
            self._state_thread.start()

            log("[DRONE]", "Connected", local_cmd_port=self.protocol.local_cmd_port, state_port=self.state_port)
            return True

        except Exception as exc:
            log("[DRONE]", "Connect failed", error=exc)
            self.close()
            return False

    def close(self):
        self._state_running = False

        if self._state_thread and self._state_thread.is_alive():
            self._state_thread.join(timeout=1.0)
        self._state_thread = None

        if self.enabled and self.protocol.is_open:
            try:
                self.protocol.send("streamoff", expect_ok=False, retries=1)
            except Exception:
                pass

        if self.state_sock:
            try:
                self.state_sock.close()
            except Exception:
                pass
            self.state_sock = None

        self.protocol.close()

    def poll_state(self) -> dict:
        with self._state_lock:
            return dict(self.state)

    def battery(self) -> int | None:
        state = self.poll_state()
        if state.get("battery_pct") is not None:
            return state["battery_pct"]

        ok, value = self.query("battery?")
        if ok:
            try:
                return int(value)
            except Exception:
                return None
        return None

    def query(self, cmd: str) -> tuple[bool, str]:
        if not self.enabled:
            return True, "sim"

        res = self.protocol.send(cmd, expect_ok=False, retries=2)
        self._track_result(res)
        if res.ok:
            return True, res.response
        if res.error_type == "error_response" and res.response:
            return True, res.response
        return False, res.response

    def recover(self) -> bool:
        if not self.enabled:
            return True

        log("[DRONE][CMD]", "Recover: emergency -> command -> streamon")

        self.protocol.send("emergency", expect_ok=False, retries=2)
        time.sleep(0.35)

        cmd = self.protocol.send("command", expect_ok=True, retries=5)
        self._track_result(cmd)

        self.protocol.send("streamoff", expect_ok=False, retries=2)
        time.sleep(0.2)

        stream = self.protocol.send("streamon", expect_ok=True, retries=4)
        self._track_result(stream)

        self.is_flying = False
        self._consecutive_timeouts = 0
        return cmd.ok and stream.ok

    def send_command(self, cmd: str) -> bool:
        if not self.enabled:
            return True

        if cmd == "recover":
            return self.recover()

        if cmd == "takeoff" and self.is_flying:
            log("[DRONE][CMD]", "Skip takeoff, already flying")
            return True
        if cmd == "land" and not self.is_flying:
            log("[DRONE][CMD]", "Skip land, already landed")
            return True

        res = self.protocol.send(cmd, expect_ok=True, retries=2)
        self._track_result(res)

        if res.ok:
            self._consecutive_timeouts = 0
            self._update_flight_on_success(cmd)
            log("[DRONE][CMD]", "Command OK", cmd=cmd, resp=res.response, rtt_ms=res.rtt_ms)
            return True

        if res.error_type == "timeout":
            self._consecutive_timeouts += 1
        else:
            self._consecutive_timeouts = 0

        log("[DRONE][CMD]", "Command failed", cmd=cmd, error_type=res.error_type, resp=res.response)

        should_recover = (cmd in ("takeoff", "land")) and (
            res.error_type in ("error_response", "timeout")
            and (res.error_type == "error_response" or self._consecutive_timeouts >= 2)
        )

        if should_recover:
            log("[DRONE][CMD]", "Auto recover policy triggered", cmd=cmd)
            if self.recover():
                retry = self.protocol.send(cmd, expect_ok=True, retries=1)
                self._track_result(retry)
                if retry.ok:
                    self._update_flight_on_success(cmd)
                    log("[DRONE][CMD]", "Retry after recover OK", cmd=cmd, resp=retry.response)
                    return True
                log("[DRONE][CMD]", "Retry after recover failed", cmd=cmd, resp=retry.response)

        if cmd == "emergency":
            self.is_flying = False

        return False

    def diagnostics(self) -> dict:
        state = self.poll_state()
        total = max(1, self._stats.cmd_total)
        return {
            "cmd_total": self._stats.cmd_total,
            "cmd_ok": self._stats.cmd_ok,
            "cmd_error": self._stats.cmd_error,
            "cmd_timeout": self._stats.cmd_timeout,
            "cmd_ok_rate": round(self._stats.cmd_ok / total, 3),
            "last_cmd": self.protocol.last_command,
            "last_resp": self.protocol.last_response,
            "last_rtt_ms": self.protocol.last_rtt_ms,
            "battery_pct": state.get("battery_pct"),
            "height_cm": state.get("height_cm"),
            "flight_state": state.get("flight_state"),
            "is_flying": self.is_flying,
            "connected": self.protocol.is_open,
        }

    def _update_flight_on_success(self, cmd: str):
        if cmd == "takeoff":
            self.is_flying = True
        elif cmd in ("land", "emergency"):
            self.is_flying = False

    def _track_result(self, result: CommandResult):
        self._stats.cmd_total += 1
        if result.ok:
            self._stats.cmd_ok += 1
        elif result.error_type == "timeout":
            self._stats.cmd_timeout += 1
        else:
            self._stats.cmd_error += 1

    def _state_loop(self):
        while self._state_running and self.state_sock:
            try:
                data, _ = self.state_sock.recvfrom(2048)
                msg = data.decode("utf-8", errors="ignore")
                telemetry = StateParser.parse(msg)
                with self._state_lock:
                    if telemetry.battery_pct is not None:
                        self.state["battery_pct"] = telemetry.battery_pct
                    if telemetry.height_cm is not None:
                        self.state["height_cm"] = telemetry.height_cm
                    self.state["flight_state"] = telemetry.flight_state

                    if telemetry.flight_state == "flying":
                        self.is_flying = True
                    elif telemetry.flight_state in ("landed", "near_ground"):
                        if telemetry.height_cm is not None and telemetry.height_cm <= 5:
                            self.is_flying = False

            except socket.timeout:
                continue
            except OSError:
                break
            except Exception as exc:
                log("[DRONE][STATE]", "State parse error", error=exc)

