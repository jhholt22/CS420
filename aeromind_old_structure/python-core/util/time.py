import time


def monotonic_ms() -> int:
    return int(time.monotonic() * 1000)


def epoch_ms() -> int:
    return int(time.time() * 1000)
