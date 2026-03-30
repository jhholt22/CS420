# AeroMind

AeroMind is a research-focused drone control system for DJI Tello (SDK 2.0) using laptop-side hand gesture inference, safety gating, and a JavaFX control UI bridge.

The drone is treated as an actuator/sensor endpoint. Gesture recognition, command decisions, safety checks, and streaming logic run on the laptop.

## Repository Layout

```text
aeromind/
  python-core/
    main.py                    # Root entrypoint (delegates to app/main.py)
    app/
      main.py                  # App startup + mode selection
      app_controller.py        # Main orchestration and loop
      runtime_config.py        # Runtime config and ports
    drone/
      drone_interface.py       # High-level Tello lifecycle/control API
      tello_protocol.py        # Serialized UDP command transport
      state_parser.py          # Tello telemetry parser
    video/
      tello_video_source.py    # Tello stream lifecycle + watchdog restart
      frame_bus.py             # Thread-safe latest-frame bus
      mjpeg_server.py          # MJPEG server (http://127.0.0.1:8080/video)
    ui/
      ui_bridge_server.py      # TCP JSON-lines bridge for Java UI
      messages.py              # UI message parsing/types
    gesture/
      gesture_model.py
      gesture_mapper.py
      safety.py
    util/
      log.py                   # Timestamped structured logs
      time.py
    camera.py                  # Webcam fallback source
    simulator.py               # Sim mode state model
    gui.py                     # OpenCV overlay and keyboard controls
    logger.py                  # CSV logging
  java-ui/                     # JavaFX UI (separate runtime)
  data/logs/                   # Run CSV outputs
  requirements.txt
  README.md
```

## Ports and Protocols

- Tello command UDP: `8889`
- Tello state UDP: `8890`
- Tello video UDP: `11111`
- UI bridge TCP (JSON lines): `127.0.0.1:7070`
- MJPEG stream: `http://127.0.0.1:8080/video`

## Run

1. Create and activate venv:
   - Windows PowerShell:
     - `python -m venv venv`
     - `.\venv\Scripts\Activate.ps1`
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Start Python runtime:
   - `python python-core/main.py`
4. Select mode when prompted:
   - `sim` for simulator
   - `drone` for DJI Tello
5. Start Java UI (separately). Python will accept reconnects on port `7070`.

## UI Command Messages

Python expects newline-delimited JSON on the UI bridge:

```json
{"type":"CMD","cmd":"takeoff"}
{"type":"CMD","cmd":"land"}
{"type":"CMD","cmd":"emergency"}
{"type":"CMD","cmd":"recover"}
{"type":"CMD","cmd":"diag"}
```

Notes:
- UI commands are rate-limited (`700ms`) except `emergency`, `recover`, and `diag`.
- `diag` prints and returns one-shot diagnostics in telemetry payload.

## Reliability Features (Python)

- Serialized command transport (single in-flight UDP command wait).
- Stable fixed local UDP command port binding.
- Recover workflow: `emergency -> command -> streamoff/streamon`.
- Auto-recover policy for `takeoff/land` on errors/timeouts with single retry.
- Telemetry loop with clean thread shutdown and state parsing.
- Video watchdog auto-restart when frames stall or decode fails.
- Java bridge reconnect-safe send/poll behavior.
- Debug panel log printed every 2 seconds with command/video/UI health stats.

## Safety Notes

- Confidence threshold + gesture stability + cooldown gates are enforced.
- Emergency gesture/command is always prioritized.
- Test in `sim` mode before real flight.
- Fly in an open indoor area and keep manual override available.
