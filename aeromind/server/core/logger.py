from __future__ import annotations

import csv
import os
from pathlib import Path


def _prune_run_logs(log_path: Path, keep: int = 20) -> None:
    if log_path.name.startswith("run_") and log_path.suffix == ".csv":
        pattern = "run_*.csv"
    elif log_path.suffix == ".log":
        pattern = "*.log"
    else:
        return

    try:
        candidates = sorted(
            (
                path for path in log_path.parent.glob(pattern)
                if path.is_file() and path != log_path
            ),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        return

    for old_path in candidates[keep - 1:]:
        try:
            old_path.unlink()
        except OSError:
            continue


class Logger:
    def __init__(self, filepath: str, header: list[str]):
        path = Path(filepath)
        os.makedirs(path.parent, exist_ok=True)
        _prune_run_logs(path)
        self._file = path.open("w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, fieldnames=header)
        self._writer.writeheader()

    def log(self, row: dict) -> None:
        self._writer.writerow(row)
        self._file.flush()

    def close(self) -> None:
        self._file.close()
