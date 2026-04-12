from __future__ import annotations

import csv
import statistics
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import time

from app.utils.logging_utils import gesture_debug_log


@dataclass(slots=True)
class _CsvTarget:
    name: str
    path: Path
    file: object
    writer: csv.DictWriter


@dataclass(slots=True)
class _LatencySummary:
    samples: list[int]

    def add(self, value: int | None) -> None:
        if value is None:
            return
        self.samples.append(int(value))

    def describe(self) -> str | None:
        if not self.samples:
            return None
        ordered = sorted(self.samples)
        return (
            f"n={len(ordered)} "
            f"avg={round(sum(ordered) / len(ordered), 1)} "
            f"median={round(statistics.median(ordered), 1)} "
            f"min={ordered[0]} "
            f"max={ordered[-1]}"
        )


class GestureLogger:
    _LOG_DIR = Path("data/logs")
    _DEFAULT_FILENAME = "gesture_research_logs.csv"
    _RUN_FILENAME_TEMPLATE = "run_{run_id}.csv"
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
        "stable_hits",
        "t_frame_capture",
        "t_inference_done",
        "t_stable_ready",
        "t_command_dispatch_start",
        "t_command_dispatch_end",
        "api_roundtrip_ms",
        "vision_to_stable_ms",
        "stable_to_dispatch_ms",
        "total_client_pipeline_ms",
        "threshold",
        "resolved_command",
        "dispatch_allowed",
        "command_sent",
        "command_block_reason",
        "inference_queue_state",
        "controller_queue_state",
        "required_hits",
        "required_confidence",
        "drone_state",
        "battery_pct",
        "height_cm",
        "command_ts_ms",
        "ack_ts_ms",
        "drone_motion_ts_ms",
        "e2e_latency_ms",
        "notes",
    ]

    def __init__(self, log_path: str | Path | None = None, *, flush_every_rows: int = 50) -> None:
        self.run_id = datetime.now().strftime("%Y%m%d%H%M%S")
        self._frame_id = 0
        self._current_label = "-"
        self._participant_id = "P001"
        self._lighting = "unknown"
        self._background = "unknown"
        self._distance_m = ""
        self._notes = ""
        self._session_active = False
        self._flush_every_rows = max(1, int(flush_every_rows))
        self._pending_rows = 0
        self._latency_summaries = {
            "vision_to_stable_ms": _LatencySummary([]),
            "stable_to_dispatch_ms": _LatencySummary([]),
            "api_roundtrip_ms": _LatencySummary([]),
            "total_client_pipeline_ms": _LatencySummary([]),
            "e2e_latency_ms": _LatencySummary([]),
        }
        self._summary_printed = False
        root_path = Path(__file__).resolve().parents[4]
        default_log_path = root_path / self._LOG_DIR / self._DEFAULT_FILENAME
        self._run_log_path = root_path / self._LOG_DIR / self._RUN_FILENAME_TEMPLATE.format(run_id=self.run_id)
        self._log_path = Path(log_path) if log_path is not None else default_log_path
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._targets: list[_CsvTarget] = [
            self._open_target("aggregate", self._log_path),
            self._open_target("run", self._run_log_path),
        ]
        gesture_debug_log(
            "gesture_logger.targets_initialized",
            aggregate_path=self._log_path,
            run_path=self._run_log_path,
            run_id=self.run_id,
        )

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

    @staticmethod
    def _normalize_bool(value: bool | None) -> str:
        if value is None:
            return ""
        return "true" if bool(value) else "false"

    @staticmethod
    def _normalize_frame_id(value: object) -> str:
        if value is None:
            return ""
        try:
            return str(int(value))
        except (TypeError, ValueError):
            text = str(value).strip()
            return text

    def close(self) -> None:
        targets = getattr(self, "_targets", None)
        if not targets:
            return
        self._print_latency_summary()
        self.flush()
        for target in targets:
            target.file.close()
        self._targets = []

    def flush(self) -> None:
        targets = getattr(self, "_targets", None)
        if not targets:
            return
        for target in targets:
            target.file.flush()
        self._pending_rows = 0

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
        self._summary_printed = False

    def end_session(self) -> None:
        self._session_active = False
        self._print_latency_summary()

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
            stable_hits=None,
            t_frame_capture=None,
            t_inference_done=None,
            t_stable_ready=None,
            t_command_dispatch_start=None,
            t_command_dispatch_end=None,
            api_roundtrip_ms=None,
            vision_to_stable_ms=None,
            stable_to_dispatch_ms=None,
            total_client_pipeline_ms=None,
            threshold=None,
            resolved_command=None,
            dispatch_allowed=None,
            command_sent="-",
            command_block_reason="-",
            inference_queue_state=None,
            controller_queue_state=None,
            required_hits=None,
            required_confidence=None,
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
            stable_hits=None,
            t_frame_capture=None,
            t_inference_done=None,
            t_stable_ready=None,
            t_command_dispatch_start=None,
            t_command_dispatch_end=None,
            api_roundtrip_ms=None,
            vision_to_stable_ms=None,
            stable_to_dispatch_ms=None,
            total_client_pipeline_ms=None,
            threshold=None,
            resolved_command=None,
            dispatch_allowed=None,
            command_sent="-",
            command_block_reason="-",
            inference_queue_state=None,
            controller_queue_state=None,
            required_hits=None,
            required_confidence=None,
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
        stable_hits: int | None = None,
        t_frame_capture: int | None = None,
        t_inference_done: int | None = None,
        t_stable_ready: int | None = None,
        t_command_dispatch_start: int | None = None,
        t_command_dispatch_end: int | None = None,
        api_roundtrip_ms: int | None = None,
        vision_to_stable_ms: int | None = None,
        stable_to_dispatch_ms: int | None = None,
        total_client_pipeline_ms: int | None = None,
        threshold: float | None = None,
        resolved_command: str | None = None,
        dispatch_allowed: bool | None = None,
        inference_queue_state: str | None = None,
        controller_queue_state: str | None = None,
        required_hits: int | None = None,
        required_confidence: float | None = None,
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
            stable_hits=stable_hits,
            t_frame_capture=t_frame_capture,
            t_inference_done=t_inference_done,
            t_stable_ready=t_stable_ready,
            t_command_dispatch_start=t_command_dispatch_start,
            t_command_dispatch_end=t_command_dispatch_end,
            api_roundtrip_ms=api_roundtrip_ms,
            vision_to_stable_ms=vision_to_stable_ms,
            stable_to_dispatch_ms=stable_to_dispatch_ms,
            total_client_pipeline_ms=total_client_pipeline_ms,
            threshold=threshold,
            resolved_command=resolved_command,
            dispatch_allowed=dispatch_allowed,
            command_sent="-",
            command_block_reason="-",
            inference_queue_state=inference_queue_state,
            controller_queue_state=controller_queue_state,
            required_hits=required_hits,
            required_confidence=required_confidence,
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
        stable_hits: int | None = None,
        t_frame_capture: int | None = None,
        t_inference_done: int | None = None,
        t_stable_ready: int | None = None,
        t_command_dispatch_start: int | None = None,
        t_command_dispatch_end: int | None = None,
        api_roundtrip_ms: int | None = None,
        vision_to_stable_ms: int | None = None,
        stable_to_dispatch_ms: int | None = None,
        total_client_pipeline_ms: int | None = None,
        threshold: float | None = None,
        resolved_command: str | None = None,
        dispatch_allowed: bool | None = None,
        command_sent: str | None = None,
        command_block_reason: str | None = None,
        inference_queue_state: str | None = None,
        controller_queue_state: str | None = None,
        required_hits: int | None = None,
        required_confidence: float | None = None,
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
            stable_hits=stable_hits,
            t_frame_capture=t_frame_capture,
            t_inference_done=t_inference_done,
            t_stable_ready=t_stable_ready,
            t_command_dispatch_start=t_command_dispatch_start,
            t_command_dispatch_end=t_command_dispatch_end,
            api_roundtrip_ms=api_roundtrip_ms,
            vision_to_stable_ms=vision_to_stable_ms,
            stable_to_dispatch_ms=stable_to_dispatch_ms,
            total_client_pipeline_ms=total_client_pipeline_ms,
            threshold=threshold,
            resolved_command=resolved_command,
            dispatch_allowed=dispatch_allowed,
            command_sent=command_sent,
            command_block_reason=command_block_reason,
            inference_queue_state=inference_queue_state,
            controller_queue_state=controller_queue_state,
            required_hits=required_hits,
            required_confidence=required_confidence,
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
        t_frame_capture: int | None = None,
        t_inference_done: int | None = None,
        t_stable_ready: int | None = None,
        t_command_dispatch_start: int | None = None,
        t_command_dispatch_end: int | None = None,
        api_roundtrip_ms: int | None = None,
        vision_to_stable_ms: int | None = None,
        stable_to_dispatch_ms: int | None = None,
        total_client_pipeline_ms: int | None = None,
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
            stable_hits=None,
            t_frame_capture=t_frame_capture,
            t_inference_done=t_inference_done,
            t_stable_ready=t_stable_ready,
            t_command_dispatch_start=t_command_dispatch_start,
            t_command_dispatch_end=t_command_dispatch_end,
            api_roundtrip_ms=api_roundtrip_ms,
            vision_to_stable_ms=vision_to_stable_ms,
            stable_to_dispatch_ms=stable_to_dispatch_ms,
            total_client_pipeline_ms=total_client_pipeline_ms,
            threshold=None,
            resolved_command=None,
            dispatch_allowed=None,
            command_sent=command_sent,
            command_block_reason="-",
            inference_queue_state=None,
            controller_queue_state=None,
            required_hits=None,
            required_confidence=None,
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
        frame_id: int | None,
        gesture_true: str | None,
        gesture_pred: str | None,
        stable_gesture: str | None,
        confidence: float | None,
        stable_ms: int | None,
        stable_hits: int | None,
        t_frame_capture: int | None,
        t_inference_done: int | None,
        t_stable_ready: int | None,
        t_command_dispatch_start: int | None,
        t_command_dispatch_end: int | None,
        api_roundtrip_ms: int | None,
        vision_to_stable_ms: int | None,
        stable_to_dispatch_ms: int | None,
        total_client_pipeline_ms: int | None,
        threshold: float | None,
        resolved_command: str | None,
        dispatch_allowed: bool | None,
        command_sent: str | None,
        command_block_reason: str | None,
        inference_queue_state: str | None,
        controller_queue_state: str | None,
        required_hits: int | None,
        required_confidence: float | None,
        drone_state: str | None,
        battery_pct: int | None,
        height_cm: int | None,
        command_ts_ms: int | None,
        ack_ts_ms: int | None,
        drone_motion_ts_ms: int | None,
        e2e_latency_ms: int | None,
        notes: str | None,
    ) -> None:
        row = {
            "run_id": self._normalize_text(self.run_id, default=""),
            "ts_ms": self._normalize_int(self._now_ms()),
            "event_type": self._normalize_text(event_type),
            "frame_id": self._normalize_frame_id(frame_id),
            "participant_id": self._normalize_text(self._participant_id, default=""),
            "lighting": self._normalize_text(self._lighting, default="unknown"),
            "background": self._normalize_text(self._background, default="unknown"),
            "distance_m": self._normalize_optional_text(self._distance_m),
            "gesture_true": self._normalize_text(gesture_true),
            "gesture_pred": self._normalize_text(gesture_pred),
            "stable_gesture": self._normalize_text(stable_gesture),
            "confidence": self._normalize_float(confidence),
            "stable_ms": self._normalize_int(stable_ms),
            "stable_hits": self._normalize_int(stable_hits),
            "t_frame_capture": self._normalize_int(t_frame_capture),
            "t_inference_done": self._normalize_int(t_inference_done),
            "t_stable_ready": self._normalize_int(t_stable_ready),
            "t_command_dispatch_start": self._normalize_int(t_command_dispatch_start),
            "t_command_dispatch_end": self._normalize_int(t_command_dispatch_end),
            "api_roundtrip_ms": self._normalize_int(api_roundtrip_ms),
            "vision_to_stable_ms": self._normalize_int(vision_to_stable_ms),
            "stable_to_dispatch_ms": self._normalize_int(stable_to_dispatch_ms),
            "total_client_pipeline_ms": self._normalize_int(total_client_pipeline_ms),
            "threshold": self._normalize_float(threshold),
            "resolved_command": self._normalize_text(resolved_command),
            "dispatch_allowed": self._normalize_bool(dispatch_allowed),
            "command_sent": self._normalize_text(command_sent),
            "command_block_reason": self._normalize_text(command_block_reason),
            "inference_queue_state": self._normalize_text(inference_queue_state),
            "controller_queue_state": self._normalize_text(controller_queue_state),
            "required_hits": self._normalize_int(required_hits),
            "required_confidence": self._normalize_float(required_confidence),
            "drone_state": self._normalize_text(drone_state),
            "battery_pct": self._normalize_int(battery_pct),
            "height_cm": self._normalize_int(height_cm),
            "command_ts_ms": self._normalize_int(command_ts_ms),
            "ack_ts_ms": self._normalize_int(ack_ts_ms),
            "drone_motion_ts_ms": self._normalize_int(drone_motion_ts_ms),
            "e2e_latency_ms": self._normalize_int(e2e_latency_ms),
            "notes": self._notes if notes is None else self._normalize_optional_text(notes),
        }
        self._append_row(row)
        self._record_latency_samples(
            event_type=event_type,
            vision_to_stable_ms=vision_to_stable_ms,
            stable_to_dispatch_ms=stable_to_dispatch_ms,
            api_roundtrip_ms=api_roundtrip_ms,
            total_client_pipeline_ms=total_client_pipeline_ms,
            e2e_latency_ms=e2e_latency_ms,
        )
        self._pending_rows += 1
        if self._pending_rows >= self._flush_every_rows:
            self.flush()

    def _open_target(self, name: str, path: Path) -> _CsvTarget:
        path.parent.mkdir(parents=True, exist_ok=True)
        rotated_from: Path | None = None
        existing_header = self._read_existing_header(path)
        if existing_header and existing_header != self._FIELDS:
            rotated_from = path.with_name(f"{path.stem}.legacy_{self.run_id}{path.suffix}")
            path.replace(rotated_from)
        file_exists = path.exists()
        file = path.open("a", newline="", encoding="utf-8")
        writer = csv.DictWriter(file, fieldnames=self._FIELDS)
        header_written = False
        if not file_exists or path.stat().st_size == 0:
            writer.writeheader()
            file.flush()
            header_written = True
        gesture_debug_log(
            "gesture_logger.target_opened",
            target=name,
            path=path,
            header_written=header_written,
            rotated_from=rotated_from,
        )
        return _CsvTarget(name=name, path=path, file=file, writer=writer)

    @staticmethod
    def _read_existing_header(path: Path) -> list[str] | None:
        if not path.exists() or path.stat().st_size == 0:
            return None
        with path.open("r", newline="", encoding="utf-8") as handle:
            try:
                return next(csv.reader(handle), None)
            except Exception:
                return None

    def _append_row(self, row: dict[str, str]) -> None:
        for target in self._targets:
            try:
                target.writer.writerow(row)
                gesture_debug_log(
                    "gesture_logger.row_appended",
                    target=target.name,
                    path=target.path,
                    event_type=row.get("event_type", "-"),
                    run_id=row.get("run_id", "-"),
                )
            except Exception as exc:
                gesture_debug_log(
                    "gesture_logger.write_failed",
                    target=target.name,
                    path=target.path,
                    event_type=row.get("event_type", "-"),
                    error=f"{type(exc).__name__}: {exc}",
                )
                raise

    def _record_latency_samples(
        self,
        *,
        event_type: str,
        vision_to_stable_ms: int | None,
        stable_to_dispatch_ms: int | None,
        api_roundtrip_ms: int | None,
        total_client_pipeline_ms: int | None,
        e2e_latency_ms: int | None,
    ) -> None:
        if event_type not in {"gesture_ready", "command_dispatch", "motion_observed"}:
            return
        self._latency_summaries["vision_to_stable_ms"].add(vision_to_stable_ms)
        self._latency_summaries["stable_to_dispatch_ms"].add(stable_to_dispatch_ms)
        self._latency_summaries["api_roundtrip_ms"].add(api_roundtrip_ms)
        self._latency_summaries["total_client_pipeline_ms"].add(total_client_pipeline_ms)
        self._latency_summaries["e2e_latency_ms"].add(e2e_latency_ms)

    def _print_latency_summary(self) -> None:
        if self._summary_printed:
            return
        summary_lines: list[str] = []
        for metric_name, summary in self._latency_summaries.items():
            description = summary.describe()
            if description is None:
                continue
            summary_lines.append(f"{metric_name} {description}")
        if not summary_lines:
            return
        print("[LATENCY SUMMARY]", flush=True)
        for line in summary_lines:
            print(f"[LATENCY SUMMARY] {line}", flush=True)
        gesture_debug_log(
            "gesture_logger.latency_summary",
            run_id=self.run_id,
            summary=" | ".join(summary_lines),
        )
        self._summary_printed = True
