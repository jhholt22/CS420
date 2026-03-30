from __future__ import annotations

from flask_restx import fields


def register_models(api):
    command_request = api.model(
        "CommandRequest",
        {
            "command": fields.String(
                required=True,
                description="Command name. Legacy raw strings like 'forward 50' are still accepted.",
                example="forward",
            ),
            "args": fields.Raw(
                required=False,
                description="Structured command arguments keyed by argument name.",
                example={"distance_cm": 50},
            ),
        },
    )

    command_response = api.model(
        "CommandResponse",
        {
            "ok": fields.Boolean(required=True, description="True when the command was accepted.", example=True),
            "command": fields.String(required=True, description="Normalized command name.", example="forward"),
            "args": fields.Raw(required=True, description="Normalized structured arguments.", example={"distance_cm": 50}),
            "raw_command": fields.String(required=True, description="Internal raw command string sent to the controller.", example="forward 50"),
        },
    )

    start_request = api.model(
        "StartRequest",
        {
            "mode": fields.String(
                required=True,
                description="Controller mode: sim or drone.",
                enum=["sim", "drone"],
                example="sim",
            ),
        },
    )

    lifecycle_response = api.model(
        "LifecycleResponse",
        {
            "started": fields.Boolean(description="True when a controller was started.", example=True),
            "stopped": fields.Boolean(description="True when a controller was stopped.", example=False),
            "already_running": fields.Boolean(description="True when start was ignored because controller already exists.", example=False),
            "was_running": fields.Boolean(description="True when stop acted on a running controller.", example=False),
            "mode": fields.String(description="Current or previous runtime mode.", example="sim"),
        },
    )

    state_response = api.model(
        "StateResponse",
        {
            "battery_pct": fields.Integer(
                description="Battery percentage.",
                example=87,
            ),
            "height_cm": fields.Integer(
                description="Height in centimeters.",
                example=120,
            ),
            "flight_state": fields.String(
                required=True,
                description="Parsed flight state.",
                example="flying",
            ),
            "is_flying": fields.Boolean(
                required=True,
                description="Whether the drone is currently flying.",
                example=True,
            ),
            "mode": fields.String(
                required=True,
                description="Current runtime mode.",
                example="drone",
            ),
        },
    )

    status_response = api.model(
        "StatusResponse",
        {
            "running": fields.Boolean(
                required=True,
                description="True when the controller is active.",
                example=True,
            ),
            "mode": fields.String(
                description="Current runtime mode.",
                example="sim",
            ),
        },
    )

    commands_response = api.model(
        "CommandsResponse",
        {
            "commands": fields.Raw(
                required=True,
                description="Command registry keyed by command name.",
                example={
                    "takeoff": {
                        "description": "Initiate drone takeoff.",
                        "args": {},
                        "category": "flight",
                    },
                    "forward": {
                        "description": "Move forward in cm.",
                        "args": {
                            "distance_cm": {
                                "type": "integer",
                                "required": True,
                                "min": 20,
                                "max": 500,
                            }
                        },
                        "category": "movement",
                    },
                },
            ),
        },
    )

    diag_response = api.model(
        "DiagResponse",
        {
            "diag": fields.Raw(
                required=True,
                description="Diagnostics payload from the controller.",
            ),
        },
    )

    error_response = api.model(
        "ErrorResponse",
        {
            "message": fields.String(
                required=True,
                description="Error message.",
                example="controller is not running",
            ),
        },
    )

    return {
        "command_request": command_request,
        "command_response": command_response,
        "start_request": start_request,
        "lifecycle_response": lifecycle_response,
        "state_response": state_response,
        "status_response": status_response,
        "commands_response": commands_response,
        "diag_response": diag_response,
        "error_response": error_response,
    }
