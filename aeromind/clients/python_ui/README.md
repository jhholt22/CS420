# AeroMind Python UI

Client application for controlling AeroMind.

---

## Features

- Displays server state
- Sends control commands
- Connects to MJPEG video stream
- Runs client-side gesture detection on live frames

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

## Gesture

Gesture inference runs in the client:

```text
video → inference → command → API
```

---

## Controls

- Buttons (UI)
- Keyboard
- Gesture

---

## Notes

- Requires server running
- Works with simulator or real drone
