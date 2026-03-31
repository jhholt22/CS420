from __future__ import annotations


class ApiClient:
    def __init__(self, base_url: str = "") -> None:
        self.base_url = base_url
