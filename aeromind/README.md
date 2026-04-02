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
- open_palm
- fist
- thumbs_up
- thumbs_down
- point_up

---

## ⚠️ Notes

Gesture control is experimental and may not always trigger commands reliably.

---

## 👤 Author

 Jihad Al Sayed
