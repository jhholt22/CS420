# 🚁 AeroMind

AeroMind is a modular drone control system for the DJI Tello (SDK 2.0).

It is built with a clean separation between:

* **Server** → drone control, REST API, simulator, video streaming
* **Client** → desktop UI, gesture inference, command dispatch

The project focuses on **real-time control and research**, especially:

> Can hand-gesture control be reliable and safe for real-time drone operation?

---

## 🧠 Architecture

```
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

```
server/
  api/            # REST API (Flask + Swagger)
  core/           # Controller, drone logic, simulator, safety
  streaming/      # Camera + MJPEG server

clients/
  python_ui/      # PySide6 UI + gesture inference

data/
  logs/           # Research / runtime logs
```

---

## ⚙️ Features

* Flask REST API
* Swagger docs → `/api/docs`
* MJPEG video stream → `/video`
* Simulator mode (safe testing)
* DJI Tello integration
* PySide6 desktop UI
* Virtual joystick + manual controls
* Gesture control (MediaPipe-based)

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

* Start Sim → safe testing
* Start Drone → real drone

---

### 4. Open video stream

```
http://127.0.0.1:8080/video
```

---

## 🎮 Controls

* Takeoff / Land
* Emergency stop
* Virtual joystick
* Start / Stop controller

---

## ✋ Gesture Control (Experimental)

Gesture control uses **MediaPipe Gesture Recognizer + hand landmark direction logic**.

### Supported Gestures (Current Build)

| Gesture         | Description          | Command   | Type       | Behavior                 |
| --------------- | -------------------- | --------- | ---------- | ------------------------ |
| ✋ **open_palm** | All fingers extended | `hover`   | Safety     | Stops movement / neutral |
| ✊ **fist**      | All fingers folded   | `land`    | One-shot   | Lands once, latched      |
| ✌️ **victory**  | Two fingers up       | `takeoff` | One-shot   | Takes off once, latched  |
| ☝️ **point_up** | Index finger up      | `forward` | Repeatable | Moves forward            |

---

### Directional Control (Tilt-Based)

Directional movement is derived from **hand orientation**, not separate gestures:

| Gesture       | Action  |
| ------------- | ------- |
| ☝️ neutral    | forward |
| ☝️ tilt left  | left    |
| ☝️ tilt right | right   |

👉 Uses hand landmarks (wrist → index direction)

---

### Gesture Design Principles

* **Terminal commands (takeoff / land)**

  * Trigger once
  * Do NOT require continuous gesture
  * Protected from accidental override

* **Safety gesture (open_palm)**

  * Always safe fallback
  * Stops movement

* **Movement gestures**

  * Continuous
  * Controlled by stabilization + cooldown

---

### Gesture Mapping (Final)

```
Open palm      → Hover / Stop
Victory        → Takeoff
Fist           → Land
Pointing up    → Forward
Point + tilt L → Left
Point + tilt R → Right
No gesture     → No command
```

---

## 🎥 Gesture Camera

* Gesture detection uses **webcam**
* Video display can remain **drone stream**

Config:

```python
gesture_webcam_index = 0
```

---

## ⚠️ Notes

* Gesture control is **experimental**
* Always test in **Simulator mode first**
* Avoid using gestures in unstable lighting conditions
* Keep gestures **clear and consistent**

---

## 🧪 Research Focus

This project explores:

* Gesture recognition reliability
* Real-time control stability
* Human-drone interaction models
* Safety constraints in gesture-based control

---

## 🔥 Current Status

* GestureRecognizer integrated ✅
* Terminal command locking working ✅
* Tilt-based control implemented ⚙️
* Stability tuning in progress ⚙️

---

## 📌 Future Improvements

* Smoother motion control (velocity scaling)
* Custom gesture training
* Multi-hand interaction
* UI gesture debug overlay
* Adaptive thresholds (lighting / distance)

---

## 👨‍💻 Author

Sayed Jihad Al Sayed

---

## 🧠 Final Note

This system is designed to **fail safe, not fail fast**.

If gesture recognition is uncertain →
👉 the drone should do nothing, not something wrong.
