from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class CommandModel:
    name: str
    args: dict[str, object] | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "command": self.name,
            "args": self.args or {},
        }
