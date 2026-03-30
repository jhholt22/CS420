# AeroMind Python UI

Client application for controlling AeroMind.

---

## Features

- Displays server state
- Sends control commands
- Connects to video stream
- Ready for gesture integration

---

## Run

```bash
python -m clients.python_ui.app.main
```

---

## Configuration

Edit inside code:

```python
API_BASE = "http://127.0.0.1:5000/api"
VIDEO_URL = "http://127.0.0.1:8080/video"
```

---

## Gesture (Planned)

Gesture inference runs here:

```text
video → inference → command → API
```

---

## Controls

- Buttons (UI)
- Keyboard (planned)
- Gesture (planned)

---

## Notes

- Requires server running
- Works with simulator or real drone
