from __future__ import annotations

import sys
import threading
from datetime import datetime
from typing import Any

_lock = threading.Lock()


def log(tag: str, message: str, **kwargs: Any) -> None:
    """
    Thread-safe structured logger.

    Example:
        log("[API]", "Controller started", mode="drone", run_id="123")
    """

    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]

    parts = [f"{ts}", tag, message]

    if kwargs:
        kv = " ".join(f"{k}={v}" for k, v in kwargs.items())
        parts.append(kv)

    line = " | ".join(parts)

    with _lock:
        print(line, file=sys.stdout, flush=True)