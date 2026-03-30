from __future__ import annotations

import csv
import os


class Logger:
    def __init__(self, filepath: str, header: list[str]):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        self._file = open(filepath, "w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, fieldnames=header)
        self._writer.writeheader()

    def log(self, row: dict) -> None:
        self._writer.writerow(row)
        self._file.flush()

    def close(self) -> None:
        self._file.close()