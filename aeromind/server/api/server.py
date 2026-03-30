from __future__ import annotations

from flask import Flask, redirect, request
from flask_restx import Namespace, Resource

from server.api.command_registry import (
    build_runtime_command,
    get_command_registry,
    normalize_command_payload,
)
from server.api.controller_service import ControllerService
from server.api.extensions import create_api_blueprint
from server.api.schemas.models import register_models
from server.core.util.log import log


def create_app(service: ControllerService | None = None) -> Flask:
    app = Flask("aeromind-api")
    controller_service = service or ControllerService()

    api_blueprint, api = create_api_blueprint()
    models = register_models(api)

    controller_ns = Namespace(
        "controller",
        description="Inspection and lifecycle endpoints for the AeroMind runtime controller.",
        path="/",
    )

    @controller_ns.route("/start")
    class StartResource(Resource):
        @controller_ns.doc(
            summary="Start controller",
            description="Starts the AeroMind controller in either sim or drone mode.",
        )
        @controller_ns.expect(models["start_request"], validate=True)
        @controller_ns.marshal_with(models["lifecycle_response"], code=200)
        @controller_ns.response(400, "Invalid request", models["error_response"])
        def post(self):
            payload = request.get_json(silent=True) or {}
            log("[API]", "Endpoint start", mode=payload.get("mode"))
            try:
                return controller_service.start(payload["mode"])
            except ValueError as exc:
                controller_ns.abort(400, str(exc))
            except KeyError:
                controller_ns.abort(400, "Missing required field: mode")

    @controller_ns.route("/stop")
    class StopResource(Resource):
        @controller_ns.doc(
            summary="Stop controller",
            description="Stops the running AeroMind controller if one is active.",
        )
        @controller_ns.marshal_with(models["lifecycle_response"], code=200)
        def post(self):
            log("[API]", "Endpoint stop")
            return controller_service.stop()

    @controller_ns.route("/commands")
    class CommandsResource(Resource):
        @controller_ns.doc(
            summary="List command registry",
            description="Returns the supported command registry. Clients use this registry to know which commands can be sent to the server.",
        )
        @controller_ns.marshal_with(models["commands_response"], code=200)
        def get(self):
            log("[API]", "Endpoint commands")
            return {"commands": get_command_registry()}

    @controller_ns.route("/state")
    class StateResource(Resource):
        @controller_ns.doc(
            summary="Get runtime state",
            description="Returns current runtime state from the active controller.",
        )
        @controller_ns.marshal_with(models["state_response"], code=200)
        @controller_ns.response(409, "Controller is not running", models["error_response"])
        def get(self):
            log("[API]", "Endpoint state")
            try:
                return controller_service.get_state()
            except RuntimeError as exc:
                controller_ns.abort(409, str(exc))

    @controller_ns.route("/diag")
    class DiagResource(Resource):
        @controller_ns.doc(
            summary="Get diagnostics",
            description="Returns diagnostics from the active controller instance.",
        )
        @controller_ns.marshal_with(models["diag_response"], code=200)
        @controller_ns.response(409, "Controller is not running", models["error_response"])
        def get(self):
            log("[API]", "Endpoint diag")
            try:
                return {"diag": controller_service.get_diag()}
            except RuntimeError as exc:
                controller_ns.abort(409, str(exc))

    @controller_ns.route("/status")
    class StatusResource(Resource):
        @controller_ns.doc(
            summary="Get controller status",
            description="Returns whether the controller is running and which mode it is using.",
        )
        @controller_ns.marshal_with(models["status_response"], code=200)
        def get(self):
            log("[API]", "Endpoint status")
            return controller_service.status()

    api.add_namespace(controller_ns)
    app.register_blueprint(api_blueprint)
    @controller_ns.route("/command")
    class CommandResource(Resource):
        @controller_ns.expect(models["command_request"], validate=False)
        @controller_ns.marshal_with(models["command_response"], code=200)
        @controller_ns.response(400, "Invalid request", models["error_response"])
        @controller_ns.response(409, "Controller is not running", models["error_response"])
        def post(self):
            payload = request.get_json(silent=True) or {}
            try:
                normalized = normalize_command_payload(payload)
            except ValueError as exc:
                controller_ns.abort(400, str(exc))

            try:
                raw_command = build_runtime_command(normalized["command"], normalized["args"])
                controller_service._get_running_controller().submit_command(raw_command)
                return {
                    "ok": True,
                    "command": normalized["command"],
                    "args": normalized["args"],
                    "raw_command": raw_command,
                }
            except RuntimeError as exc:
                controller_ns.abort(409, str(exc))
    @app.get("/swagger")
    def swagger_redirect():
        return redirect("/api/docs", code=302)

    @app.get("/docs")
    def docs_redirect():
        return redirect("/api/docs", code=302)

    @app.get("/health")
    def health():
        return {
            "ok": True,
            "service": "aeromind-api",
            **controller_service.status(),
        }

    log("[API]", "Flask app created")
    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, threaded=True)
