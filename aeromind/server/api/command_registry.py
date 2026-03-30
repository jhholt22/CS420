from __future__ import annotations

from copy import deepcopy


COMMAND_REGISTRY = {
    "takeoff": {
        "description": "Initiate drone takeoff.",
        "args": {},
        "category": "flight",
    },
    "land": {
        "description": "Land the drone safely.",
        "args": {},
        "category": "flight",
    },
    "emergency": {
        "description": "Immediately stop all motors.",
        "args": {},
        "category": "safety",
    },
    "recover": {
        "description": "Run emergency recovery and restore the video stream.",
        "args": {},
        "category": "safety",
    },
    "forward": {
        "description": "Move forward by a configured distance in centimeters.",
        "args": {
            "distance_cm": {
                "type": "integer",
                "required": True,
                "min": 20,
                "max": 500,
            },
        },
        "category": "movement",
    },
    "back": {
        "description": "Move backward by a configured distance in centimeters.",
        "args": {
            "distance_cm": {
                "type": "integer",
                "required": True,
                "min": 20,
                "max": 500,
            },
        },
        "category": "movement",
    },
    "cw": {
        "description": "Rotate clockwise by a number of degrees.",
        "args": {
            "degrees": {
                "type": "integer",
                "required": True,
                "min": 1,
                "max": 360,
            },
        },
        "category": "rotation",
    },
    "ccw": {
        "description": "Rotate counter-clockwise by a number of degrees.",
        "args": {
            "degrees": {
                "type": "integer",
                "required": True,
                "min": 1,
                "max": 360,
            },
        },
        "category": "rotation",
    },
    "diag": {
        "description": "Trigger a diagnostics snapshot on the running controller.",
        "args": {},
        "category": "system",
    },
}


def get_command_registry() -> dict:
    return deepcopy(COMMAND_REGISTRY)