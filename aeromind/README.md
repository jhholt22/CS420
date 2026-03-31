# AeroMind

AeroMind is a modular drone control system for DJI Tello (SDK 2.0) with a clean separation between:

- Server (drone control + API + video streaming)
- Client (UI + gesture inference)

The system is designed to be extensible, testable, and production-ready.


disconnect the firewall
---

## Architecture

```text
Client (Python UI)
    ↓
HTTP API (Flask + Swagger)
    ↓
Controller Service
    ↓
Drone / Simulator
    ↓
Video Stream (MJPEG)
```

---

## Project Structure

```text
server/
  api/            # REST API (Flask + Swagger)
  core/           # Controller, drone logic, safety, gesture core
  streaming/      # Camera + MJPEG server

clients/
  python_ui/      # UI + gesture inference

data/
  logs/           # Runtime logs
```

---

## Features

- REST API for drone control
- Swagger documentation (`/api/docs`)
- MJPEG video streaming (`/video`)
- Simulator mode for testing
- Thread-safe controller lifecycle
- Client-side gesture-ready architecture

---

## Quick Start

### 1. Start API

```bash
python -m server.api
```

Open:

```text
http://127.0.0.1:5000/api/docs
```

---

### 2. Start Controller

```http
POST /api/start
Content-Type: application/json

{
  "mode": "sim"
}
```

---

### 3. Open Video Stream

```text
http://127.0.0.1:8080/video
```

---

### 4. Run Client UI

```bash
python -m clients.python_ui.app.main
```

---

## Controls

The client UI provides:

- Takeoff / Land
- Forward / Back
- Rotate (CW / CCW)
- Emergency stop

Keyboard support (planned):
- Arrow keys → movement
- Space → takeoff
- ESC → land

---

## Gesture Integration (Client-side)

Gesture inference is designed to run on the client, not the server.

Flow:

```text
Video Stream → Client → Gesture Model → Command → API → Drone
```

This avoids:
- server overload
- latency issues
- tight coupling

---

## API Endpoints

Base URL: `/api`

- `POST /start`
- `POST /stop`
- `GET /status`
- `GET /state`
- `GET /diag`
- `GET /commands`
- `POST /command`

Swagger:

```text
/api/docs
```

---

## Modes

### Simulator
- No drone required
- Safe testing
- Immediate feedback

### Drone
- Connects to DJI Tello
- Uses UDP protocol

---

## Safety

- Emergency command always available
- Cooldown enforced in client/server
- Test in `sim` before real drone

---

## Future Improvements

- Real gesture recognition (MediaPipe)
- Continuous control (joystick-like)
- Web-based UI
- Multi-drone support
- Command validation via schema

---

## Philosophy

- Keep server simple and deterministic
- Move intelligence (AI/gesture) to client
- Design for expansion, not hacks

---

## Author

Sayed Jihad Al Sayed
