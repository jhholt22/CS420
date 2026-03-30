import threading
from datetime import datetime

_lock = threading.Lock()


def _fmt_kv(fields: dict) -> str:
    if not fields:
        return ""
    parts = []
    for k, v in fields.items():
        parts.append(f"{k}={v}")
    return " " + " ".join(parts)


def log(tag: str, message: str, **fields):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    line = f"{ts} {tag} {message}{_fmt_kv(fields)}"
    with _lock:
        print(line)
