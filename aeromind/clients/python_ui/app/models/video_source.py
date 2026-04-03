from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

VideoSourceKind = Literal["mjpeg", "webcam"]


@dataclass(frozen=True, slots=True)
class VideoSourceSpec:
    kind: VideoSourceKind
    value: str | int
    label: str

    @classmethod
    def mjpeg(cls, url: str) -> VideoSourceSpec:
        return cls(kind="mjpeg", value=url.strip(), label="MJPEG")

    @classmethod
    def webcam(cls, index: int) -> VideoSourceSpec:
        return cls(kind="webcam", value=index, label=f"Webcam {index}")

    @property
    def descriptor(self) -> str:
        return f"{self.kind}:{self.value}"
