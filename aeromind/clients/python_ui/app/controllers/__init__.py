from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = [
    "AppController",
    "CommandController",
    "GestureController",
    "RcController",
]

if TYPE_CHECKING:
    from app.controllers.app_controller import AppController
    from app.controllers.command_controller import CommandController
    from app.controllers.gesture_controller import GestureController
    from app.controllers.rc_controller import RcController


def __getattr__(name: str) -> Any:
    if name == "AppController":
        from app.controllers.app_controller import AppController

        return AppController
    if name == "CommandController":
        from app.controllers.command_controller import CommandController

        return CommandController
    if name == "GestureController":
        from app.controllers.gesture_controller import GestureController

        return GestureController
    if name == "RcController":
        from app.controllers.rc_controller import RcController

        return RcController
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
