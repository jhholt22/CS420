from __future__ import annotations

from flask import Blueprint
from flask_restx import Api


def create_api_blueprint() -> tuple[Blueprint, Api]:
    blueprint = Blueprint("aeromind_api", __name__, url_prefix="/api")
    api = Api(
        blueprint,
        version="1.0",
        title="AeroMind API",
        description="HTTP API for controlling and inspecting the AeroMind runtime controller.",
        doc="/docs",
        ordered=True,
    )
    return blueprint, api