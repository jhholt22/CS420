import csv
import os

class Logger:
    def __init__(self, filepath: str, header: list[str]):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        self.f = open(filepath, "w", newline="", encoding="utf-8")
        self.w = csv.DictWriter(self.f, fieldnames=header)
        self.w.writeheader()

    def log(self, row: dict):
        self.w.writerow(row)
        self.f.flush()

    def close(self):
        self.f.close()
