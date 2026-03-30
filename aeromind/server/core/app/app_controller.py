from __future__ import annotations

import threading
from dataclasses import dataclass
from queue import Empty, Queue
from typing import Any

from server.core.app.runtime_config import RuntimeConfig
from server.core.drone.drone_interface import DroneInterface
from server.core.gesture.gesture_mapper import GestureMapper
from server.core.gesture.gesture_model import GestureModel
from server.core.gesture.safety import SafetyDecision, SafetyLayer
from server.core.logger import Logger
from server.core.simulator import Simulator
from server.core.util.log import log
from server.core.util.time import epoch_ms
from server.streaming.camera.camera import Camera
from server.streaming.frame_bus import FrameBus
from server.streaming.mjpeg_server import MjpegServer
from server.streaming.tello_video_source import TelloVideoSource

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
        self.model = GestureModel()
        self.mapper = GestureMapper()
        self.safety = SafetyLayer(
            cfg.conf_threshold,
            cfg.stable_window_ms,
            cfg.command_cooldown_ms,
        )
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

        self.camera: Camera | TelloVideoSource | None = None
        self.running = False

        self._cmd_queue: Queue[CommandTask] = Queue(maxsize=64)
        self._cmd_thread: threading.Thread | None = None
        self._cmd_running = False
        self._video_restart_lock = threading.Lock()

        self._frame_id = 0
        self._participant_id = "P1"

        self._last_pred: Any = None
        self._last_cand: Any = None
        self._last_decision = SafetyDecision(False, "none", "none")

        self._queued_count = 0
        self._executed_ok = 0
        self._executed_err = 0

    def start(self) -> None:
        log("[APP]", "Starting", run_id=self.cfg.run_id, mode="drone" if self.use_drone else "sim")

        self.mjpeg.start()

        ok = self.drone.connect()
        if self.use_drone and not ok:
            log("[APP]", "Drone connect failed, fallback to SIM")
            self.drone.enabled = False

        if self.use_drone and self.drone.enabled:
            self.camera = TelloVideoSource(
                self.drone,
                video_url=self.cfg.tello_video_url,
                warmup_s=self.cfg.video_warmup_s,
                watchdog_s=self.cfg.video_watchdog_s,
                stall_reads=self.cfg.video_stall_reads,
            )
            if not self.camera.start():
                log("[VIDEO]", "Tello stream init failed, fallback webcam")
                self.camera.release()
                self.camera = Camera()
        else:
            self.camera = Camera()

        self._cmd_running = True
        self._cmd_thread = threading.Thread(
            target=self._command_worker,
            name="cmd-worker",
            daemon=True,
        )
        self._cmd_thread.start()

        self.running = True
        log("[APP]", "Started")

    def stop(self) -> None:
        self.running = False
        self._cmd_running = False

        if self._cmd_thread and self._cmd_thread.is_alive():
            self._cmd_thread.join(timeout=1.5)
        self._cmd_thread = None

        if self.camera:
            self.camera.release()

        self.drone.close()
        self.mjpeg.stop()
        self.logger.close()

        log("[APP]", "Stopped")

    def run(self) -> None:
        self.start()

        try:
            while self.running:
                if not self.camera:
                    break

                now_ms = epoch_ms()
                ok, frame = self.camera.read()

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
                    self._frame_id += 1

        finally:
            self.stop()

    def submit_command(self, cmd: str, source: str = "api") -> None:
        cmd_normalized = cmd.strip().lower()
        if cmd_normalized == "diag":
            self._handle_diag_command()
            return
        self._enqueue_command(cmd_normalized, source=source)

    def get_api_state(self) -> dict:
        state = self.drone.poll_state() or {}
        return {
            "battery_pct": state.get("battery_pct"),
            "height_cm": state.get("height_cm"),
            "flight_state": state.get("flight_state") or "unknown",
            "is_flying": self.drone.is_flying,
            "mode": "drone" if self.drone.enabled else "sim",
        }

    def get_api_status(self) -> dict:
        return {
            "running": self.running,
            "mode": "drone" if self.drone.enabled else "sim",
        }

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
        }

    def _enqueue_command(self, cmd: str, source: str) -> None:
        try:
            self._cmd_queue.put_nowait(CommandTask(cmd=cmd, source=source, ts_ms=epoch_ms()))
            self._queued_count += 1
        except Exception:
            log("[DRONE][CMD]", "Command queue full, dropped", cmd=cmd, source=source)

    def _command_worker(self) -> None:
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

            if ok or not self.drone.enabled:
                self.sim.apply(cmd)

            log("[DRONE][CMD]", "Executed", cmd=cmd, source=task.source, ok=ok)

    def _restart_video_blocking(self, reason: str) -> None:
        if not self.camera or not hasattr(self.camera, "restart_stream"):
            return

        if not self._video_restart_lock.acquire(blocking=False):
            return

        try:
            log("[VIDEO]", "Restart requested", reason=reason)
            self.camera.restart_stream()
        finally:
            self._video_restart_lock.release()

    def _log_frame(self, ts_ms: int, pred: Any, cand: Any, decision: SafetyDecision) -> None:
        self.logger.log({
            "run_id": self.cfg.run_id,
            "ts_ms": ts_ms,
            "event_type": "frame",
            "frame_id": self._frame_id,
            "participant_id": self._participant_id,
            "lighting": self.cfg.lighting,
            "background": self.cfg.background,
            "distance_m": self.cfg.distance_m,
            "gesture_true": "",
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

    def _handle_diag_command(self) -> None:
        diag = self.collect_diag()
        log("[API]", "diag requested", **diag)