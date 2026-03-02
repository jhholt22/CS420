import socket
import threading
import time


class DroneInterface:
    TELLO_IP = "192.168.10.1"
    CMD_PORT = 8889
    STATE_PORT = 8890

    def __init__(
        self,
        enabled: bool = False,
        *,
        local_cmd_port: int = 9000,   # fixed local port = stable reconnect
        cmd_timeout: float = 3.0,
    ):
        self.enabled = enabled
        self.local_cmd_port = local_cmd_port
        self.cmd_timeout = cmd_timeout
        self.is_flying = False
        self.cmd_sock: socket.socket | None = None
        self.state_sock: socket.socket | None = None

        self.state = {"battery_pct": None, "height_cm": None}

        self._running = False
        self._state_thread: threading.Thread | None = None
        self._cmd_lock = threading.Lock()

    # ---------------------------
    # Public API
    # ---------------------------
    def connect(self) -> bool:
        if not self.enabled:
            print("[Drone] SIM mode")
            return True

        # if you call connect twice, do the safe thing
        self.close()

        try:
            print("[Drone] Connecting to Tello...")

            # Command socket: bind to a FIXED local port
            self.cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.cmd_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.cmd_sock.bind(("0.0.0.0", self.local_cmd_port))
            self.cmd_sock.settimeout(self.cmd_timeout)

            # State socket: bind to 8890 for telemetry
            self.state_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.state_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.state_sock.bind(("0.0.0.0", self.STATE_PORT))
            self.state_sock.settimeout(0.2)  # small timeout so loop can stop fast

            # Enter SDK mode (retry because UDP can drop)
            self._send_cmd("command", expect_ok=True, retries=5)

            # Start telemetry thread (NOT daemon) so we can join on shutdown
            self._running = True
            self._state_thread = threading.Thread(target=self._state_loop, name="tello-state")
            self._state_thread.start()

            print("[Drone] Connected (SDK mode)")
            return True

        except Exception as e:
            print(f"[Drone] Connection failed: {e}")
            self.close()
            return False

    def send_command(self, cmd: str) -> bool:
        if not self.enabled:
            return True

        # local gating
        if cmd == "takeoff" and self.is_flying:
            print("[Drone] Ignored takeoff (already flying)")
            return True
        if cmd == "land" and not self.is_flying:
            print("[Drone] Ignored land (not flying)")
            return True

        try:
            # special recover sequence
            if cmd == "recover":
                print("[Drone] Recover: emergency -> command -> streamon")
                # kill motors (if needed)
                try:
                    self._send_cmd("emergency", expect_ok=True, retries=1)
                except Exception as e:
                    print(f"[Drone] Recover emergency failed: {e}")

                time.sleep(1.0)

                # re-enter sdk mode
                self._send_cmd("command", expect_ok=True, retries=5)

                # restart video stream
                try:
                    self._send_cmd("streamoff", expect_ok=False, retries=1)
                except:
                    pass
                try:
                    self._send_cmd("streamon", expect_ok=True, retries=3)
                except Exception as e:
                    print(f"[Drone] Recover streamon failed: {e}")

                self.is_flying = False
                return True

            # normal command
            self._send_cmd(cmd, expect_ok=True, retries=2)

            # update local state if command succeeded
            if cmd == "takeoff":
                self.is_flying = True
            elif cmd in ("land", "emergency"):
                self.is_flying = False

            return True

        except Exception as e:
            print(f"[Drone] Command failed ({cmd}): {e}")
            return False
    def poll_state(self):
        return self.state

    def close(self):
        # try to stop stream first while socket still alive
        if self.enabled and self.cmd_sock:
            try:
                # dont retry much on shutdown
                self._send_cmd("streamoff", expect_ok=False, retries=1)
            except:
                pass

        # stop thread
        self._running = False
        if self._state_thread and self._state_thread.is_alive():
            self._state_thread.join(timeout=1.0)
        self._state_thread = None

        # close sockets
        if self.state_sock:
            try: self.state_sock.close()
            except: pass
            self.state_sock = None

        if self.cmd_sock:
            try: self.cmd_sock.close()
            except: pass
            self.cmd_sock = None
    
    # ---------------------------
    # Internals
    # ---------------------------
    def _state_loop(self):
        while self._running and self.state_sock:
            try:
                data, _ = self.state_sock.recvfrom(2048)
                self._parse_state(data.decode("utf-8", errors="ignore"))
            except socket.timeout:
                continue
            except OSError:
                # socket got closed while waiting
                break
            except Exception:
                continue

    def _parse_state(self, msg: str):
        parts = msg.strip().split(";")
        for p in parts:
            if ":" not in p:
                continue
            k, v = p.split(":", 1)
            if k == "bat":
                try:
                    self.state["battery_pct"] = int(v)
                except:
                    pass
            elif k == "h":
                try:
                    self.state["height_cm"] = int(v)
                except:
                    pass
            elif k == "h":
                try:
                    self.state["height_cm"] = int(v)
                    if self.state["height_cm"] <= 5:
                        self.is_flying = False
                except:
                    pass

    def _send_cmd(self, cmd: str, *, expect_ok: bool, retries: int = 1) -> str:
        if not self.cmd_sock:
            raise RuntimeError("Command socket not initialized")

        last_err: Exception | None = None

        # IMPORTANT: lock so only one command waits for a response at a time
        with self._cmd_lock:
            for _ in range(max(1, retries)):
                try:
                    self.cmd_sock.sendto(cmd.encode("utf-8"), (self.TELLO_IP, self.CMD_PORT))
                    data, _ = self.cmd_sock.recvfrom(1024)
                    resp = data.decode("utf-8", errors="ignore").strip()

                    if resp.lower() == "error" and expect_ok:
                        raise RuntimeError("Tello returned error")

                    if expect_ok and resp.lower() != "ok":
                        raise RuntimeError(f"Unexpected response: {resp}")

                    return resp

                except Exception as e:
                    last_err = e
                    time.sleep(0.15)

        raise last_err if last_err else RuntimeError("Unknown send_cmd failure")