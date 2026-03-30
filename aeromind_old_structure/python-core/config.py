RUN_ID = None  # filled in main

CONF_THRESHOLD = 0.80
STABLE_WINDOW_MS = 400
COMMAND_COOLDOWN_MS = 900

# experiment metadata defaults (can be overridden per run)
LIGHTING = "normal"        # normal | low
BACKGROUND = "clean"       # clean | cluttered
DISTANCE_M = 0.5           # 0.5 | 1.0

# gestures
GESTURES = [
    "takeoff",
    "land",
    "forward",
    "backward",
    "rotate_left",
    "emergency_stop",
    "none",
]
