"""
AeroMind - main.py

This file is the ENTRY POINT of the system.

Responsibilities:
- Wire all modules together
- Control the main loop
- Decide sim vs real drone
- Coordinate camera, model, safety, GUI, logging

IMPORTANT:
- No ML logic here
- No drone protocol logic here
- No heavy UI logic here
"""

import time
from datetime import datetime

import cv2

from camera import Camera
from gesture_model import GestureModel
from gesture_mapper import GestureMapper
from safety import SafetyLayer
from drone_interface import DroneInterface
from simulator import Simulator
from logger import Logger
from gui import GUI
import config

from ui_bridge_server import UiBridgeServer
# =========================
# CSV LOGGER SCHEMA
# =========================
CSV_HEADER = [
    "run_id","ts_ms","event_type","frame_id","participant_id","lighting","background","distance_m",
    "gesture_true","gesture_pred","confidence","stable_ms","threshold",
    "command_sent","command_block_reason",
    "drone_state","battery_pct","height_cm",
    "command_ts_ms","ack_ts_ms","drone_motion_ts_ms",
    "e2e_latency_ms","notes"
]


def now_ms() -> int:
    """Return current time in milliseconds."""
    return int(time.time() * 1000)


def main():
    """
    Main application loop.
    This function runs until the user quits.
    """

    # =========================
    # RUN / EXPERIMENT METADATA
    # =========================
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    config.RUN_ID = run_id

    participant_id = "P1"  # CHANGE per participant during experiments

    print(f"[AeroMind] Run ID: {run_id}")

    # =========================
    # MODE SELECTION
    # =========================
    mode = input("Mode? (sim/drone): ").strip().lower()
    use_drone = (mode == "drone")

    # =========================
    # LOGGER SETUP
    # =========================
    log_path = f"data/logs/run_{run_id}.csv"
    logger = Logger(log_path, CSV_HEADER)

    # =========================
    # MODULE INITIALIZATION
    # =========================
    cam = Camera()
    model = GestureModel()
    mapper = GestureMapper()
    safety = SafetyLayer(
        config.CONF_THRESHOLD,
        config.STABLE_WINDOW_MS,
        config.COMMAND_COOLDOWN_MS
    )

    drone = DroneInterface(enabled=use_drone)
    sim = Simulator()
    gui = GUI()
    ui = UiBridgeServer()
    ui.start()
    # =========================
    # DRONE CONNECTION
    # =========================
 
    ok = drone.connect()
    if use_drone and not ok:
        print("[WARN] Drone connection failed. Falling back to SIM.")
        drone.enabled = False

    if use_drone and drone.enabled:
        from tello_video_source import TelloVideoSource
        cam = TelloVideoSource(drone)

        if not cam.start():
            print("[WARN] Tello video failed. Falling back to webcam.")
            cam.release()
            cam = Camera()
    else:
        cam = Camera()


    # =========================
    # MAIN LOOP STATE
    # =========================
    frame_id = 0
    print("[AeroMind] System started. Press 'q' to quit.")

    try:
        # =========================
        # MAIN LOOP
        # =========================
        while gui.running:
            # ---- UI COMMANDS FROM JAVA ----
            for msg in ui.poll():
                if msg.get("type") == "CMD" and drone.enabled:
                    cmd = msg.get("cmd", "")
                    if cmd == "emergency":
                        drone.send_command("emergency")
                    elif cmd in ("takeoff", "land"):
                        drone.send_command(cmd)
            ts = now_ms()

            # ---- CAMERA ----
            ok, frame = cam.read()
            if not ok or frame is None:
                continue

            # ---- GESTURE PREDICTION ----
            pred = model.predict(frame)

            # ---- GESTURE STABILITY + MAPPING ----
            cand = mapper.update(ts, pred.gesture)

            # ---- SAFETY DECISION ----
            decision = safety.decide(
                ts_ms=ts,
                gesture=pred.gesture,
                confidence=pred.confidence,
                stable_ms=cand.stable_ms,
                command=cand.command
            )

            # =========================
            # FRAME-LEVEL LOGGING
            # =========================
            logger.log({
                "run_id": run_id,
                "ts_ms": ts,
                "event_type": "frame",
                "frame_id": frame_id,
                "participant_id": participant_id,
                "lighting": config.LIGHTING,
                "background": config.BACKGROUND,
                "distance_m": config.DISTANCE_M,
                "gesture_true": gui.gesture_true,   # manual label from GUI
                "gesture_pred": pred.gesture,
                "confidence": pred.confidence,
                "stable_ms": cand.stable_ms,
                "threshold": config.CONF_THRESHOLD,
                "command_sent": decision.command if decision.allowed else "none",
                "command_block_reason": decision.reason,
                "drone_state": "",
                "battery_pct": "",
                "height_cm": "",
                "command_ts_ms": "",
                "ack_ts_ms": "",
                "drone_motion_ts_ms": "",
                "e2e_latency_ms": "",
                "notes": ""
            })

            # =========================
            # COMMAND EXECUTION
            # =========================
            if decision.allowed and decision.command != "none":
                cmd_ts = now_ms()

                # send to drone (or noop in sim)
                drone.send_command(decision.command)

                # update simulator mirror
                sim.apply(decision.command)

                state = drone.poll_state()

                # ---- COMMAND-LEVEL LOGGING ----
                logger.log({
                    "run_id": run_id,
                    "ts_ms": cmd_ts,
                    "event_type": "command",
                    "frame_id": frame_id,
                    "participant_id": participant_id,
                    "lighting": config.LIGHTING,
                    "background": config.BACKGROUND,
                    "distance_m": config.DISTANCE_M,
                    "gesture_true": gui.gesture_true,
                    "gesture_pred": pred.gesture,
                    "confidence": pred.confidence,
                    "stable_ms": cand.stable_ms,
                    "threshold": config.CONF_THRESHOLD,
                    "command_sent": decision.command,
                    "command_block_reason": "none",
                    "drone_state": str(sim.snapshot()),
                    "battery_pct": state.get("battery_pct"),
                    "height_cm": state.get("height_cm"),
                    "command_ts_ms": cmd_ts,
                    "ack_ts_ms": "",
                    "drone_motion_ts_ms": "",
                    "e2e_latency_ms": "",
                    "notes": ""
                })

            # =========================
            # GUI RENDERING
            # =========================
            gui.draw(
                frame=frame,
                pred=pred,
                decision=decision,
                sim_state=sim.snapshot()
            )

            # keyboard handling (quit / labeling)
            gui.handle_keys()
            # ---- TELEMETRY TO JAVA UI ----
            # ---- TELEMETRY TO JAVA UI ----
            state = drone.poll_state()

            ui.send({
                "type": "telemetry",
                "ts_ms": ts,
                "pred_gesture": pred.gesture,
                "confidence": pred.confidence,
                "stable_ms": cand.stable_ms,
                "candidate_cmd": cand.command,
                "decision_allowed": decision.allowed,
                "block_reason": decision.reason,
                "battery_pct": state.get("battery_pct") if state else None,
                "height_cm": state.get("height_cm") if state else None,
                "mode": "drone" if drone.enabled else "sim",
            })
            frame_id += 1

    finally:
        # =========================
        # CLEAN SHUTDOWN
        # =========================
        print("[AeroMind] Shutting down.")
        cam.release()
        gui.close()
        drone.close()   # <-- ADD THIS
        ui.stop()
        logger.close()


# =========================
# ENTRY POINT
# =========================
if __name__ == "__main__":
    main()
