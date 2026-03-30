# AeroMind Server

Handles:

- Drone control
- Controller lifecycle
- REST API
- Video streaming

---

## Run

```bash
python -m server.api
```

---

## API

Swagger:

```text
http://127.0.0.1:5000/api/docs
```

---

## Video

```text
http://127.0.0.1:8080/video
```

---

## Components

- `api/` → Flask API
- `core/` → controller + drone + safety
- `streaming/` → camera + MJPEG

---

## Notes

- Server streams frames and executes validated commands from the client
- Server is stateless except controller lifecycle
