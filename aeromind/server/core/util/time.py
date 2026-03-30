from __future__ import annotations

import time


def epoch_ms() -> int:
    """
    Current time in milliseconds since epoch.
    """
    return int(time.time() * 1000)


def now_s() -> float:
    """
    High-resolution current time in seconds.
    """
    return time.perf_counter()


def sleep_ms(ms: int) -> None:
    """
    Sleep for given milliseconds.
    """
    time.sleep(ms / 1000.0)