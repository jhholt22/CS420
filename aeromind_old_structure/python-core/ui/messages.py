from dataclasses import dataclass


@dataclass
class UiCommand:
    cmd: str


@dataclass
class TelemetryMessage:
    payload: dict


def parse_ui_message(msg: dict) -> UiCommand | None:
    if not isinstance(msg, dict):
        return None
    if msg.get("type") != "CMD":
        return None
    cmd = str(msg.get("cmd", "")).strip()
    if not cmd:
        return None
    return UiCommand(cmd=cmd)
