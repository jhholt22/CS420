# 🚁 AeroMind

AeroMind is a modular drone control system for the DJI Tello (SDK 2.0).

It is designed with a clean separation between:

- **Server** → drone control, REST API, simulator, video streaming  
- **Client** → desktop UI, gesture inference, command dispatch  

The project focuses on **real-time control and research**, especially exploring:

> Can hand-gesture control be reliable and safe for real-time drone operation?

---

## 🧠 Architecture

```text
Client (PySide6 UI)
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

## 📁 Project Structure

```text
server/
  api/            # REST API (Flask + Swagger)
  core/           # Controller, drone logic, simulator, safety
  streaming/      # Camera + MJPEG server

clients/
  python_ui/      # PySide6 UI + gesture inference

data/
  logs/           # Research / runtime logs (if enabled)
```

---

## ⚙️ Features

- Flask REST API  
- Swagger docs → /api/docs  
- MJPEG video stream → /video  
- Simulator mode (safe testing)  
- DJI Tello integration  
- PySide6 desktop UI  
- Virtual joystick + manual controls  
- Experimental gesture recognition (MediaPipe-based)  

---

## 🚀 Quick Start

### 1. Start backend API

```bash
python -m server.api
```

Open Swagger:

```
http://127.0.0.1:5000/api/docs
```

---

### 2. Start UI

```bash
python clients/python_ui/main.py
```

---

### 3. Start controller

From UI:
- Start Sim → safe testing  
- Start Drone → real drone  

---

### 4. Open video stream

```
http://127.0.0.1:8080/video
```

---

## 🎮 Controls

- Takeoff / Land  
- Emergency stop  
- Virtual joystick  
- Start / Stop controller  

---

## ✋ Gesture Control (Experimental)

Uses MediaPipe for hand tracking.

Supported gestures:
| Gesture Name        | Shape Description               | Command          | Type       | Behavior                     |
| ------------------- | ------------------------------- | ---------------- | ---------- | ---------------------------- |
| **thumbs_up**       | Thumb up, others folded         | `takeoff`        | One-shot   | Fires once, requires release | try left hand 
| **fist**            | All fingers folded              | `land`           | One-shot   | Fires once, requires release | work
| **open_palm**       | All fingers extended            | `stop` / neutral | Safety     | Stops movement / resets      | work
| **point_up**        | Index up, others folded         | `forward`        | Repeatable | Moves forward with cooldown  | work
| **point_left**      | Index pointing left             | `left`           | Repeatable | Moves left with cooldown     | 
| **point_right**     | Index pointing right            | `right`          | Repeatable | Moves right with cooldown    |
| **L-shape (right)** | Thumb + index (L shape → right) | `rotate_right`   | Repeatable | Rotates right in bursts      |
| **L-shape (left)**  | Thumb + index (L shape → left)  | `rotate_left`    | Repeatable | Rotates left in bursts       |


---

## ⚠️ Notes

Gesture control is experimental and may not always trigger commands reliably.
 
