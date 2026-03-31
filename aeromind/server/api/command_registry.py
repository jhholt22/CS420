from __future__ import annotations

from copy import deepcopy
from typing import Any


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
    "left": {
        "description": "Move left by a configured distance in centimeters.",
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
    "right": {
        "description": "Move right by a configured distance in centimeters.",
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
    "up": {
        "description": "Move up by a configured distance in centimeters.",
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
    "down": {
        "description": "Move down by a configured distance in centimeters.",
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
    "rc": {
        "description": "Continuous joystick control using Tello rc left_right forward_back up_down yaw.",
        "args": {
            "left_right": {
                "type": "integer",
                "required": True,
                "min": -100,
                "max": 100,
            },
            "forward_back": {
                "type": "integer",
                "required": True,
                "min": -100,
                "max": 100,
            },
            "up_down": {
                "type": "integer",
                "required": True,
                "min": -100,
                "max": 100,
            },
            "yaw": {
                "type": "integer",
                "required": True,
                "min": -100,
                "max": 100,
            },
        },
        "category": "movement",
    },
    "stop": {
        "description": "Stop the drone and hover in place.",
        "args": {},
        "category": "safety",
    },
    "diag": {
        "description": "Trigger a diagnostics snapshot on the running controller.",
        "args": {},
        "category": "system",
    },
}


def get_command_registry() -> dict:
    return deepcopy(COMMAND_REGISTRY)


def normalize_command_payload(payload: Any) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")

    raw_command = payload.get("command")
    if not isinstance(raw_command, str) or not raw_command.strip():
        raise ValueError("Missing command")

    raw_args = payload.get("args", {})
    if raw_args is None:
        raw_args = {}
    if not isinstance(raw_args, dict):
        raise ValueError("args must be an object")

    command_text = raw_command.strip().lower()
    if raw_args:
        command_name = command_text
        args = dict(raw_args)
    else:
        command_name, args = _parse_legacy_command(command_text)

    spec = COMMAND_REGISTRY.get(command_name)
    if spec is None:
        raise ValueError(f"Unsupported command: {command_name}")

    normalized_args = _validate_args(command_name, args, spec["args"])
    return {
        "command": command_name,
        "args": normalized_args,
    }


def build_runtime_command(command: str, args: dict[str, Any]) -> str:
    spec = COMMAND_REGISTRY[command]
    if not spec["args"]:
        return command

    ordered_values = [str(args[arg_name]) for arg_name in spec["args"].keys()]
    return " ".join([command, *ordered_values])


def _parse_legacy_command(command_text: str) -> tuple[str, dict[str, Any]]:
    parts = command_text.split()
    command_name = parts[0]
    spec = COMMAND_REGISTRY.get(command_name)
    if spec is None:
        return command_name, {}

    arg_specs = spec["args"]
    if not arg_specs:
        if len(parts) > 1:
            raise ValueError(f"Command '{command_name}' does not accept args")
        return command_name, {}

    arg_names = list(arg_specs.keys())
    if len(parts) - 1 != len(arg_names):
        raise ValueError(f"Command '{command_name}' requires args: {', '.join(arg_names)}")

    parsed_args: dict[str, Any] = {}
    for arg_name, raw_value in zip(arg_names, parts[1:]):
        parsed_args[arg_name] = raw_value

    return command_name, parsed_args


def _validate_args(command: str, args: dict[str, Any], arg_specs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}

    for arg_name, spec in arg_specs.items():
        if arg_name not in args:
            if spec.get("required"):
                raise ValueError(f"Command '{command}' requires arg '{arg_name}'")
            continue

        value = args[arg_name]
        if spec.get("type") == "integer":
            try:
                value = int(value)
            except (TypeError, ValueError):
                raise ValueError(f"Arg '{arg_name}' for command '{command}' must be an integer") from None

            min_value = spec.get("min")
            max_value = spec.get("max")
            if min_value is not None and value < min_value:
                raise ValueError(f"Arg '{arg_name}' for command '{command}' must be >= {min_value}")
            if max_value is not None and value > max_value:
                raise ValueError(f"Arg '{arg_name}' for command '{command}' must be <= {max_value}")

        normalized[arg_name] = value

    unexpected_args = sorted(set(args.keys()) - set(arg_specs.keys()))
    if unexpected_args:
        raise ValueError(
            f"Unexpected args for command '{command}': {', '.join(unexpected_args)}"
        )

    return normalized
