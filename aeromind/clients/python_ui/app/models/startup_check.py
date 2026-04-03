from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


StartupStatus = Literal["ok", "warning", "failed"]


@dataclass(slots=True)
class StartupCheckItem:
    subsystem: str
    status: StartupStatus
    reason: str
    next_action: str


@dataclass(slots=True)
class StartupSummary:
    items: list[StartupCheckItem]

    @property
    def overall_status(self) -> StartupStatus:
        if any(item.status == "failed" for item in self.items):
            return "failed"
        if any(item.status == "warning" for item in self.items):
            return "warning"
        return "ok"
