import threading
from dataclasses import dataclass
from queue import Empty, Queue

from camera import Camera
from gui import GUI
from logger import Logger
from simulator import Simulator

from app.runtime_config import RuntimeConfig
from drone.drone_interface import DroneInterface
from gesture.gesture_mapper import GestureMapper
from gesture.gesture_model import GestureModel
from gesture.safety import SafetyDecision, SafetyLayer
from ui.messages import parse_ui_message
from ui.ui_bridge_server import UiBridgeServer
from util.log import log
from util.time import epoch_ms, monotonic_ms
from video.frame_bus import FrameBus
from video.mjpeg_server import MjpegServer
from video.tello_video_source import TelloVideoSource

CSV_HEADER = [
    "run_id", "ts_ms", "event_type", "frame_id", "participant_id", "lighting", "background", "distance_m",
    "gesture_true", "gesture_pred", "confidence", "stable_ms", "threshold",
    "command_sent", "command_block_reason",
    "drone_state", "battery_pct", "height_cm",
    "command_ts_ms", "ack_ts_ms", "drone_motion_ts_ms",
    "e2e_latency_ms", "notes",
]


@dataclass
class CommandTask:
    cmd: str
    source: str
    ts_ms: int


class AppController:
    def __init__(self, use_drone: bool, cfg: RuntimeConfig):
        self.cfg = cfg
        self.use_drone = use_drone

        self.logger = Logger(f"data/logs/run_{cfg.run_id}.csv", CSV_HEADER)
        self.gui = GUI()
        self.model = GestureModel()
        self.mapper = GestureMapper()
        self.safety = SafetyLayer(cfg.conf_threshold, cfg.stable_window_ms, cfg.command_cooldown_ms)
        self.sim = Simulator()

        self.drone = DroneInterface(
            enabled=use_drone,
            tello_ip=cfg.tello_ip,
            cmd_port=cfg.tello_cmd_port,
            state_port=cfg.tello_state_port,
            local_cmd_port=cfg.local_cmd_port,
            cmd_timeout=cfg.cmd_timeout_s,
        )

        self.frame_bus = FrameBus()
        self.mjpeg = MjpegServer(
            frame_bus=self.frame_bus,
            host=cfg.mjpeg_host,
            port=cfg.mjpeg_port,
            fps=cfg.mjpeg_fps,
            jpeg_quality=cfg.mjpeg_jpeg_quality,
        )

        self.ui = UiBridgeServer(host=cfg.ui_host, port=cfg.ui_port)

        self.cam = None
        self.running = False

        self._cmd_queue: Queue[CommandTask] = Queue(maxsize=64)
        self._cmd_thread = None
        self._cmd_running = False
        self._video_restart_lock = threading.Lock()

        self._frame_id = 0
        self._participant_id = "P1"
        self._last_ui_cmd_ms = -10**18

        self._last_pred = None
        self._last_cand = None
        self._last_decision = SafetyDecision(False, "none", "none")

        self._next_telemetry_ms = 0
        self._next_debug_ms = 0

        self._queued_count = 0
        self._executed_ok = 0
        self._executed_err = 0

    def start(self):
        log("[APP]", "Starting", run_id=self.cfg.run_id, mode="drone" if self.use_drone else "sim")

        self.ui.start()
        self.mjpeg.start()

        ok = self.drone.connect()
        if self.use_drone and not ok:
            log("[APP]", "Drone connect failed, fallback to SIM")
            self.drone.enabled = False

        if self.use_drone and self.drone.enabled:
            self.cam = TelloVideoSource(
                self.drone,
                video_url=self.cfg.tello_video_url,
                warmup_s=self.cfg.video_warmup_s,
                watchdog_s=self.cfg.video_watchdog_s,
                stall_reads=self.cfg.video_stall_reads,
            )
            if not self.cam.start():
                log("[VIDEO]", "Tello stream init failed, fallback webcam")
                self.cam.release()
                self.cam = Camera()
        else:
            self.cam = Camera()

        self._cmd_running = True
        self._cmd_thread = threading.Thread(target=self._command_worker, name="cmd-worker", daemon=True)
        self._cmd_thread.start()

        self.running = True

    def stop(self):
        self.running = False
        self._cmd_running = False

        if self._cmd_thread and self._cmd_thread.is_alive():
            self._cmd_thread.join(timeout=1.5)
        self._cmd_thread = None

        if self.cam:
            self.cam.release()
        self.gui.close()
        self.drone.close()
        self.ui.stop()
        self.mjpeg.stop()
        self.logger.close()

        log("[APP]", "Stopped")

    def run(self):
        self.start()
        log("[APP]", "System started", hint="Press q to quit")

        try:
            while self.gui.running:
                now_ms = epoch_ms()

                self._poll_ui_commands(now_ms)

                ok, frame = self.cam.read()
                if ok and frame is not None:
                    self.frame_bus.publish(frame)

                    pred = self.model.predict(frame)
                    cand = self.mapper.update(now_ms, pred.gesture)
                    decision = self.safety.decide(
                        ts_ms=now_ms,
                        gesture=pred.gesture,
                        confidence=pred.confidence,
                        stable_ms=cand.stable_ms,
                        command=cand.command,
                    )

                    self._last_pred = pred
                    self._last_cand = cand
                    self._last_decision = decision

                    if decision.allowed and decision.command != "none":
                        self._enqueue_command(decision.command, source="gesture")

                    self._log_frame(now_ms, pred, cand, decision)

                    self.gui.draw(frame=frame, pred=pred, decision=decision, sim_state=self.sim.snapshot())
                    self.gui.handle_keys()

                    self._frame_id += 1
                else:
                    self.gui.handle_keys()

                self._send_telemetry_if_due(now_ms)
                self._print_debug_if_due(now_ms)

        finally:
            self.stop()

    def _poll_ui_commands(self, now_ms: int):
        for raw in self.ui.poll():
            cmd_msg = parse_ui_message(raw)
            if not cmd_msg:
                continue

            cmd = cmd_msg.cmd.lower()
            if cmd == "diag":
                self._handle_diag_command()
                continue

            if cmd not in ("emergency", "recover"):
                if now_ms - self._last_ui_cmd_ms < self.cfg.ui_command_min_interval_ms:
                    log("[UI]", "Command rate-limited", cmd=cmd)
                    continue

            self._last_ui_cmd_ms = now_ms
            self._enqueue_command(cmd, source="ui")

    def _enqueue_command(self, cmd: str, source: str):
        try:
            self._cmd_queue.put_nowait(CommandTask(cmd=cmd, source=source, ts_ms=epoch_ms()))
            self._queued_count += 1
        except Exception:
            log("[DRONE][CMD]", "Command queue full, dropped", cmd=cmd, source=source)

    def _command_worker(self):
        while self._cmd_running:
            try:
                task = self._cmd_queue.get(timeout=0.2)
            except Empty:
                continue

            cmd = task.cmd
            ok = True

            if self.drone.enabled:
                if cmd == "recover":
                    ok = self.drone.recover()
                    self._restart_video_blocking("recover")
                else:
                    ok = self.drone.send_command(cmd)
                    if cmd in ("land", "emergency"):
                        self._restart_video_blocking(cmd)

            if ok:
                self._executed_ok += 1
            else:
                self._executed_err += 1

            # simulator mirror should remain available in both modes
            if ok or not self.drone.enabled:
                self.sim.apply(cmd)

            log("[DRONE][CMD]", "Executed", cmd=cmd, source=task.source, ok=ok)

    def _restart_video_blocking(self, reason: str):
        if not hasattr(self.cam, "restart_stream"):
            return

        if not self._video_restart_lock.acquire(blocking=False):
            return

        try:
            log("[VIDEO]", "Restart requested", reason=reason)
            self.cam.restart_stream()
        finally:
            self._video_restart_lock.release()

    def _log_frame(self, ts_ms: int, pred, cand, decision):
        self.logger.log({
            "run_id": self.cfg.run_id,
            "ts_ms": ts_ms,
            "event_type": "frame",
            "frame_id": self._frame_id,
            "participant_id": self._participant_id,
            "lighting": self.cfg.lighting,
            "background": self.cfg.background,
            "distance_m": self.cfg.distance_m,
            "gesture_true": self.gui.gesture_true,
            "gesture_pred": pred.gesture,
            "confidence": pred.confidence,
            "stable_ms": cand.stable_ms,
            "threshold": self.cfg.conf_threshold,
            "command_sent": decision.command if decision.allowed else "none",
            "command_block_reason": decision.reason,
            "drone_state": "",
            "battery_pct": "",
            "height_cm": "",
            "command_ts_ms": "",
            "ack_ts_ms": "",
            "drone_motion_ts_ms": "",
            "e2e_latency_ms": "",
            "notes": "",
        })

    def _send_telemetry_if_due(self, now_ms: int):
        if now_ms < self._next_telemetry_ms:
            return

        interval_ms = max(10, int(1000.0 / max(1.0, self.cfg.telemetry_hz)))
        self._next_telemetry_ms = now_ms + interval_ms

        state = self.drone.poll_state()
        pred_gesture = self._last_pred.gesture if self._last_pred else "none"
        conf = self._last_pred.confidence if self._last_pred else 0.0
        stable_ms = self._last_cand.stable_ms if self._last_cand else 0
        candidate_cmd = self._last_cand.command if self._last_cand else "none"

        self.ui.send({
            "type": "telemetry",
            "ts_ms": now_ms,
            "pred_gesture": pred_gesture,
            "confidence": conf,
            "stable_ms": stable_ms,
            "candidate_cmd": candidate_cmd,
            "decision_allowed": self._last_decision.allowed,
            "block_reason": self._last_decision.reason,
            "battery_pct": state.get("battery_pct") if state else None,
            "height_cm": state.get("height_cm") if state else None,
            "flight_state": state.get("flight_state") if state else "unknown",
            "is_flying": self.drone.is_flying,
            "mode": "drone" if self.drone.enabled else "sim",
        })

    def _print_debug_if_due(self, now_ms: int):
        if now_ms < self._next_debug_ms:
            return
        self._next_debug_ms = now_ms + int(self.cfg.debug_panel_interval_s * 1000)

        diag = self.collect_diag()
        log(
            "[DEBUG]",
            "panel",
            cmd_ok_rate=diag["cmd_ok_rate"],
            last_cmd=diag["last_cmd"],
            last_resp=diag["last_resp"],
            battery=diag["battery_pct"],
            height=diag["height_cm"],
            is_flying=diag["is_flying"],
            video_fps=diag["video_fps"],
            frame_age_ms=diag["frame_age_ms"],
            java_client=diag["java_client_connected"],
        )

    def collect_diag(self) -> dict:
        drone_diag = self.drone.diagnostics()
        frame_age_ms = self.frame_bus.frame_age_ms()
        video_fps = round(self.frame_bus.fps_estimate(), 2)

        total_exec = max(1, self._executed_ok + self._executed_err)
        exec_ok_rate = round(self._executed_ok / total_exec, 3)

        return {
            **drone_diag,
            "exec_ok": self._executed_ok,
            "exec_err": self._executed_err,
            "exec_ok_rate": exec_ok_rate,
            "queued": self._queued_count,
            "video_fps": video_fps,
            "frame_age_ms": frame_age_ms,
            "java_client_connected": self.ui.has_client,
        }

    def _handle_diag_command(self):
        diag = self.collect_diag()
        log("[UI]", "diag requested", **diag)
        self.ui.send({
            "type": "telemetry",
            "ts_ms": epoch_ms(),
            "diag": diag,
            "mode": "drone" if self.drone.enabled else "sim",
        })
