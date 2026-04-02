from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from time import time


class GestureLogger:
    _FIELDS = [
        "run_id",
        "ts_ms",
        "event_type",
        "frame_id",
        "participant_id",
        "lighting",
        "background",
        "distance_m",
        "gesture_true",
        "gesture_pred",
        "stable_gesture",
        "confidence",
        "stable_ms",
        "threshold",
        "command_sent",
        "command_block_reason",
        "drone_state",
        "battery_pct",
        "height_cm",
        "command_ts_ms",
        "ack_ts_ms",
        "drone_motion_ts_ms",
        "e2e_latency_ms",
        "notes",
    ]

    def __init__(self, log_path: str | Path | None = None) -> None:
        self.run_id = datetime.now().strftime("%Y%m%d%H%M%S")
        self._frame_id = 0
        self._current_label = "-"
        self._participant_id = "P001"
        self._lighting = "unknown"
        self._background = "unknown"
        self._distance_m = ""
        self._notes = ""
        self._session_active = False
        root_path = Path(__file__).resolve().parents[4]
        self._log_path = Path(log_path) if log_path is not None else root_path / "gesture_research_logs.csv"
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        file_exists = self._log_path.exists()
        self._file = self._log_path.open("a", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, fieldnames=self._FIELDS)
        if not file_exists or self._log_path.stat().st_size == 0:
            self._writer.writeheader()
            self._file.flush()

    @staticmethod
    def _now_ms() -> int:
        return int(time() * 1000)

    @staticmethod
    def _normalize_text(value: object, default: str = "-") -> str:
        if value is None:
            return default
        text = str(value).strip()
        if not text:
            return default
        return text

    @staticmethod
    def _normalize_optional_text(value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def _normalize_float(value: float | None) -> str:
        if value is None:
            return ""
        return f"{float(value):.6f}"

    @staticmethod
    def _normalize_int(value: int | None) -> str:
        if value is None:
            return ""
        return str(int(value))

    def close(self) -> None:
        if getattr(self, "_file", None) is None:
            return
        self._file.flush()
        self._file.close()

    def set_current_label(self, label: str) -> None:
        normalized = self._normalize_text(label)
        self._current_label = "-" if normalized == "no_label" else normalized

    def clear_current_label(self) -> None:
        self._current_label = "-"

    def get_current_label(self) -> str:
        return self._current_label

    def set_session_context(
        self,
        participant_id: str,
        lighting: str,
        background: str,
        distance_m: str,
        notes: str = "",
    ) -> None:
        self._participant_id = self._normalize_text(participant_id, default="P001")
        self._lighting = self._normalize_text(lighting, default="unknown")
        self._background = self._normalize_text(background, default="unknown")
        self._distance_m = self._normalize_optional_text(distance_m)
        self._notes = self._normalize_optional_text(notes)

    def get_session_context(self) -> dict[str, str]:
        return {
            "participant_id": self._participant_id,
            "lighting": self._lighting,
            "background": self._background,
            "distance_m": self._distance_m,
            "notes": self._notes,
        }

    def start_session(self) -> None:
        self._session_active = True

    def end_session(self) -> None:
        self._session_active = False

    def is_session_active(self) -> bool:
        return self._session_active

    def next_frame_id(self) -> int:
        self._frame_id += 1
        return self._frame_id

    def log_session_event(self, *, event_type: str, notes: str | None = None) -> None:
        self._write_row(
            event_type=event_type,
            frame_id=self.next_frame_id(),
            gesture_true=self._current_label,
            gesture_pred="-",
            stable_gesture="-",
            confidence=None,
            stable_ms=None,
            threshold=None,
            command_sent="-",
            command_block_reason="-",
            drone_state="-",
            battery_pct=None,
            height_cm=None,
            command_ts_ms=None,
            ack_ts_ms=None,
            drone_motion_ts_ms=None,
            e2e_latency_ms=None,
            notes=notes,
        )

    def log_label_change(self, *, notes: str | None = None) -> None:
        self._write_row(
            event_type="label_change",
            frame_id=self.next_frame_id(),
            gesture_true=self._current_label,
            gesture_pred="-",
            stable_gesture="-",
            confidence=None,
            stable_ms=None,
            threshold=None,
            command_sent="-",
            command_block_reason="-",
            drone_state="-",
            battery_pct=None,
            height_cm=None,
            command_ts_ms=None,
            ack_ts_ms=None,
            drone_motion_ts_ms=None,
            e2e_latency_ms=None,
            notes=notes,
        )

    def log_gesture_event(
        self,
        *,
        frame_id: int,
        gesture_true: str | None = None,
        gesture_pred: str | None = None,
        stable_gesture: str | None = None,
        confidence: float | None = None,
        stable_ms: int | None = None,
        threshold: float | None = None,
        drone_state: str | None = None,
        battery_pct: int | None = None,
        height_cm: int | None = None,
        notes: str | None = None,
    ) -> None:
        if not self._session_active:
            return
        self._write_row(
            event_type="gesture_eval",
            frame_id=frame_id,
            gesture_true=self._current_label if gesture_true is None else gesture_true,
            gesture_pred=gesture_pred,
            stable_gesture=stable_gesture,
            confidence=confidence,
            stable_ms=stable_ms,
            threshold=threshold,
            command_sent="-",
            command_block_reason="-",
            drone_state=drone_state,
            battery_pct=battery_pct,
            height_cm=height_cm,
            command_ts_ms=None,
            ack_ts_ms=None,
            drone_motion_ts_ms=None,
            e2e_latency_ms=None,
            notes=notes,
        )

    def log_command_event(
        self,
        *,
        event_type: str,
        frame_id: int,
        gesture_pred: str | None = None,
        stable_gesture: str | None = None,
        confidence: float | None = None,
        stable_ms: int | None = None,
        threshold: float | None = None,
        command_sent: str | None = None,
        command_block_reason: str | None = None,
        drone_state: str | None = None,
        battery_pct: int | None = None,
        height_cm: int | None = None,
        command_ts_ms: int | None = None,
        ack_ts_ms: int | None = None,
        notes: str | None = None,
    ) -> None:
        if not self._session_active:
            return
        self._write_row(
            event_type=event_type,
            frame_id=frame_id,
            gesture_true=self._current_label,
            gesture_pred=gesture_pred,
            stable_gesture=stable_gesture,
            confidence=confidence,
            stable_ms=stable_ms,
            threshold=threshold,
            command_sent=command_sent,
            command_block_reason=command_block_reason,
            drone_state=drone_state,
            battery_pct=battery_pct,
            height_cm=height_cm,
            command_ts_ms=command_ts_ms,
            ack_ts_ms=ack_ts_ms,
            drone_motion_ts_ms=None,
            e2e_latency_ms=None,
            notes=notes,
        )

    def log_motion_event(
        self,
        *,
        frame_id: int,
        command_sent: str | None = None,
        drone_state: str | None = None,
        battery_pct: int | None = None,
        height_cm: int | None = None,
        command_ts_ms: int | None = None,
        ack_ts_ms: int | None = None,
        drone_motion_ts_ms: int | None = None,
        e2e_latency_ms: int | None = None,
        notes: str | None = None,
    ) -> None:
        if not self._session_active:
            return
        self._write_row(
            event_type="motion_observed",
            frame_id=frame_id,
            gesture_true=self._current_label,
            gesture_pred="-",
            stable_gesture="-",
            confidence=None,
            stable_ms=None,
            threshold=None,
            command_sent=command_sent,
            command_block_reason="-",
            drone_state=drone_state,
            battery_pct=battery_pct,
            height_cm=height_cm,
            command_ts_ms=command_ts_ms,
            ack_ts_ms=ack_ts_ms,
            drone_motion_ts_ms=drone_motion_ts_ms,
            e2e_latency_ms=e2e_latency_ms,
            notes=notes,
        )

    def _write_row(
        self,
        *,
        event_type: str,
        frame_id: int,
        gesture_true: str | None,
        gesture_pred: str | None,
        stable_gesture: str | None,
        confidence: float | None,
        stable_ms: int | None,
        threshold: float | None,
        command_sent: str | None,
        command_block_reason: str | None,
        drone_state: str | None,
        battery_pct: int | None,
        height_cm: int | None,
        command_ts_ms: int | None,
        ack_ts_ms: int | None,
        drone_motion_ts_ms: int | None,
        e2e_latency_ms: int | None,
        notes: str | None,
    ) -> None:
        self._writer.writerow(
            {
                "run_id": self.run_id,
                "ts_ms": self._now_ms(),
                "event_type": self._normalize_text(event_type),
                "frame_id": int(frame_id),
                "participant_id": self._participant_id,
                "lighting": self._lighting,
                "background": self._background,
                "distance_m": self._distance_m,
                "gesture_true": self._normalize_text(gesture_true),
                "gesture_pred": self._normalize_text(gesture_pred),
                "stable_gesture": self._normalize_text(stable_gesture),
                "confidence": self._normalize_float(confidence),
                "stable_ms": self._normalize_int(stable_ms),
                "threshold": self._normalize_float(threshold),
                "command_sent": self._normalize_text(command_sent),
                "command_block_reason": self._normalize_text(command_block_reason),
                "drone_state": self._normalize_text(drone_state),
                "battery_pct": self._normalize_int(battery_pct),
                "height_cm": self._normalize_int(height_cm),
                "command_ts_ms": self._normalize_int(command_ts_ms),
                "ack_ts_ms": self._normalize_int(ack_ts_ms),
                "drone_motion_ts_ms": self._normalize_int(drone_motion_ts_ms),
                "e2e_latency_ms": self._normalize_int(e2e_latency_ms),
                "notes": self._notes if notes is None else self._normalize_optional_text(notes),
            }
        )
        self._file.flush()
