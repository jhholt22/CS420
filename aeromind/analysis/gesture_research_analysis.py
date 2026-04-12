from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_UI_ROOT = PROJECT_ROOT / "clients" / "python_ui"
if str(PYTHON_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_UI_ROOT))

from app.gestures.registry import GESTURE_REGISTRY


COMMAND_BY_GESTURE = {gesture.internal_name: gesture.command for gesture in GESTURE_REGISTRY}

EXPECTED_COLUMNS = [
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


def resolve_csv_path(argv: list[str]) -> Path:
    if len(argv) > 1 and argv[1].strip():
        return Path(argv[1]).expanduser().resolve()
    preferred = Path("data/logs/gesture_research_logs.csv").resolve()
    if preferred.exists():
        return preferred
    return Path("gesture_research_logs.csv").resolve()


def load_csv(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise SystemExit(f"CSV file not found: {csv_path}")

    try:
        dataframe = pd.read_csv(csv_path)
    except pd.errors.EmptyDataError as exc:
        raise SystemExit(f"CSV file is empty: {csv_path}") from exc
    except Exception as exc:  # pragma: no cover - defensive path
        raise SystemExit(f"Failed to read CSV file {csv_path}: {exc}") from exc

    if dataframe.empty:
        raise SystemExit(f"CSV file contains no rows: {csv_path}")

    for column in EXPECTED_COLUMNS:
        if column not in dataframe.columns:
            dataframe[column] = pd.NA

    return dataframe


def normalize_text_series(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip()


def is_meaningful_label(series: pd.Series) -> pd.Series:
    normalized = normalize_text_series(series).str.lower()
    return (~normalized.isin(["", "-", "nan", "none", "no_label"]))


def to_numeric_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def safe_rate(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return float(numerator) / float(denominator)


def round_metric(value: float | None, digits: int = 4) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def build_labeled_eval_rows(dataframe: pd.DataFrame) -> pd.DataFrame:
    eval_rows = dataframe[normalize_text_series(dataframe["event_type"]) == "gesture_eval"].copy()
    labeled_mask = is_meaningful_label(eval_rows["gesture_true"])
    return eval_rows[labeled_mask].copy()


def compute_reliability_metrics(dataframe: pd.DataFrame) -> dict[str, Any]:
    eval_rows = dataframe[normalize_text_series(dataframe["event_type"]) == "gesture_eval"].copy()
    labeled_rows = build_labeled_eval_rows(dataframe)

    raw_match = normalize_text_series(labeled_rows["gesture_pred"]) == normalize_text_series(labeled_rows["gesture_true"])
    stable_match = normalize_text_series(labeled_rows["stable_gesture"]) == normalize_text_series(labeled_rows["gesture_true"])

    confusion = pd.crosstab(
        normalize_text_series(labeled_rows["gesture_true"]),
        normalize_text_series(labeled_rows["stable_gesture"]),
        dropna=False,
    ).sort_index(axis=0).sort_index(axis=1)

    per_gesture_counts = normalize_text_series(labeled_rows["gesture_true"]).value_counts().sort_index()

    return {
        "total_gesture_eval_rows": int(len(eval_rows)),
        "total_labeled_rows": int(len(labeled_rows)),
        "raw_prediction_accuracy": round_metric(raw_match.mean() if len(labeled_rows) else None),
        "stable_gesture_accuracy": round_metric(stable_match.mean() if len(labeled_rows) else None),
        "per_gesture_counts": {str(key): int(value) for key, value in per_gesture_counts.items()},
        "confusion_matrix": confusion,
    }


def compute_safety_metrics(dataframe: pd.DataFrame) -> dict[str, Any]:
    event_type = normalize_text_series(dataframe["event_type"])
    dispatch_rows = dataframe[event_type == "command_dispatch"].copy()
    blocked_rows = dataframe[event_type == "command_blocked"].copy()

    command_rows = dataframe[normalize_text_series(dataframe["command_sent"]) != "-"].copy()
    labeled_command_rows = command_rows[is_meaningful_label(command_rows["gesture_true"])].copy()
    expected_command = normalize_text_series(labeled_command_rows["gesture_true"]).map(COMMAND_BY_GESTURE).fillna("")
    actual_command = normalize_text_series(labeled_command_rows["command_sent"])
    false_command_mask = actual_command != expected_command

    blocked_breakdown = (
        normalize_text_series(blocked_rows["command_block_reason"])
        .replace("", "unknown")
        .value_counts()
        .sort_index()
    )

    total_command_events = len(dispatch_rows) + len(blocked_rows)

    return {
        "total_command_dispatch_rows": int(len(dispatch_rows)),
        "total_command_blocked_rows": int(len(blocked_rows)),
        "command_dispatch_rate": round_metric(safe_rate(len(dispatch_rows), total_command_events)),
        "blocked_command_rate": round_metric(safe_rate(len(blocked_rows), total_command_events)),
        "blocked_reasons_breakdown": {str(key): int(value) for key, value in blocked_breakdown.items()},
        "false_command_count": int(false_command_mask.sum()),
        "false_command_rate": round_metric(
            safe_rate(false_command_mask.sum(), len(labeled_command_rows))
        ),
    }


def summarize_latency(series: pd.Series) -> dict[str, Any]:
    clean = to_numeric_series(series).dropna()
    if clean.empty:
        return {
            "count": 0,
            "average": None,
            "median": None,
            "min": None,
            "max": None,
        }

    return {
        "count": int(clean.count()),
        "average": round_metric(clean.mean()),
        "median": round_metric(clean.median()),
        "min": round_metric(clean.min()),
        "max": round_metric(clean.max()),
    }


def compute_latency_metrics(dataframe: pd.DataFrame) -> dict[str, Any]:
    event_type = normalize_text_series(dataframe["event_type"])
    dispatch_rows = dataframe[event_type == "command_dispatch"].copy()
    blocked_rows = dataframe[event_type == "command_blocked"].copy()
    ready_rows = dataframe[event_type == "gesture_ready"].copy()
    motion_rows = dataframe[event_type == "motion_observed"].copy()

    api_latency = to_numeric_series(dispatch_rows["ack_ts_ms"]) - to_numeric_series(dispatch_rows["command_ts_ms"])
    e2e_latency = to_numeric_series(dataframe["e2e_latency_ms"])
    vision_to_stable = to_numeric_series(pd.concat([dispatch_rows["vision_to_stable_ms"], ready_rows["vision_to_stable_ms"]]))
    stable_to_dispatch = to_numeric_series(dispatch_rows["stable_to_dispatch_ms"])
    client_pipeline = to_numeric_series(dispatch_rows["total_client_pipeline_ms"])
    api_roundtrip = to_numeric_series(dispatch_rows["api_roundtrip_ms"])

    stage_averages = {
        "vision_to_stable_ms": round_metric(vision_to_stable.mean() if not vision_to_stable.dropna().empty else None),
        "stable_to_dispatch_ms": round_metric(stable_to_dispatch.mean() if not stable_to_dispatch.dropna().empty else None),
        "api_roundtrip_ms": round_metric(api_roundtrip.mean() if not api_roundtrip.dropna().empty else None),
    }
    dominant_stage = None
    non_null_stage_averages = {key: value for key, value in stage_averages.items() if value is not None}
    if non_null_stage_averages:
        dominant_stage = max(non_null_stage_averages, key=non_null_stage_averages.get)

    return {
        "gesture_ready_count": int(len(ready_rows)),
        "command_dispatch_count": int(len(dispatch_rows)),
        "command_blocked_count": int(len(blocked_rows)),
        "motion_observed_count": int(len(motion_rows)),
        "vision_to_stable_ms": summarize_latency(vision_to_stable),
        "stable_to_dispatch_ms": summarize_latency(stable_to_dispatch),
        "api_roundtrip_ms": summarize_latency(api_roundtrip),
        "total_client_pipeline_ms": summarize_latency(client_pipeline),
        "api_latency_ms": summarize_latency(api_latency),
        "end_to_end_latency_ms": summarize_latency(e2e_latency),
        "dominant_delay_stage": dominant_stage,
    }


def compute_group_robustness(dataframe: pd.DataFrame, column_name: str) -> list[dict[str, Any]]:
    labeled_rows = build_labeled_eval_rows(dataframe)
    if labeled_rows.empty:
        return []

    grouped_rows = labeled_rows.copy()
    grouped_rows[column_name] = normalize_text_series(grouped_rows[column_name]).replace("", "unknown")
    grouped_rows["stable_match"] = (
        normalize_text_series(grouped_rows["stable_gesture"])
        == normalize_text_series(grouped_rows["gesture_true"])
    )
    grouped_rows["confidence_num"] = to_numeric_series(grouped_rows["confidence"])

    results: list[dict[str, Any]] = []
    for group_value, group in grouped_rows.groupby(column_name, dropna=False):
        results.append(
            {
                "group": str(group_value),
                "labeled_row_count": int(len(group)),
                "stable_gesture_accuracy": round_metric(group["stable_match"].mean()),
                "average_confidence": round_metric(group["confidence_num"].mean()),
            }
        )

    return sorted(results, key=lambda item: item["group"])


def compute_robustness_metrics(dataframe: pd.DataFrame) -> dict[str, Any]:
    return {
        "lighting": compute_group_robustness(dataframe, "lighting"),
        "background": compute_group_robustness(dataframe, "background"),
        "distance_m": compute_group_robustness(dataframe, "distance_m"),
    }


def confusion_matrix_to_dict(confusion: pd.DataFrame) -> dict[str, dict[str, int]]:
    if confusion.empty:
        return {}
    result: dict[str, dict[str, int]] = {}
    for row_label, row in confusion.iterrows():
        result[str(row_label)] = {str(column): int(value) for column, value in row.items()}
    return result


def save_outputs(
    csv_path: Path,
    dataframe: pd.DataFrame,
    confusion: pd.DataFrame,
    reliability: dict[str, Any],
    safety: dict[str, Any],
    latency: dict[str, Any],
    robustness: dict[str, Any],
) -> None:
    output_dir = csv_path.parent
    confusion_path = output_dir / "confusion_matrix.csv"
    summary_path = output_dir / "summary_metrics.json"

    confusion.to_csv(confusion_path)

    summary_payload = {
        "source_csv": str(csv_path),
        "overview": {
            "row_count": int(len(dataframe)),
            "run_count": int(normalize_text_series(dataframe["run_id"]).replace("", pd.NA).dropna().nunique()),
            "participant_count": int(
                normalize_text_series(dataframe["participant_id"]).replace("", pd.NA).dropna().nunique()
            ),
        },
        "reliability": {
            key: value
            for key, value in reliability.items()
            if key != "confusion_matrix"
        },
        "safety": safety,
        "latency": latency,
        "robustness": robustness,
        "confusion_matrix": confusion_matrix_to_dict(confusion),
    }

    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(summary_payload, handle, indent=2)


def print_section(title: str) -> None:
    print(f"\n{title}")
    print("-" * len(title))


def print_key_value(label: str, value: Any) -> None:
    print(f"{label}: {value}")


def print_group_report(title: str, rows: list[dict[str, Any]]) -> None:
    print(f"{title}:")
    if not rows:
        print("  No data")
        return
    for row in rows:
        print(
            "  "
            f"{row['group']} | "
            f"count={row['labeled_row_count']} | "
            f"stable_acc={row['stable_gesture_accuracy']} | "
            f"avg_conf={row['average_confidence']}"
        )


def print_report(
    dataframe: pd.DataFrame,
    reliability: dict[str, Any],
    safety: dict[str, Any],
    latency: dict[str, Any],
    robustness: dict[str, Any],
) -> None:
    run_count = normalize_text_series(dataframe["run_id"]).replace("", pd.NA).dropna().nunique()
    participant_count = normalize_text_series(dataframe["participant_id"]).replace("", pd.NA).dropna().nunique()

    print_section("Overview")
    print_key_value("Rows", int(len(dataframe)))
    print_key_value("Runs", int(run_count))
    print_key_value("Participants", int(participant_count))
    print_key_value("Source event types", sorted(normalize_text_series(dataframe["event_type"]).unique().tolist()))

    print_section("Reliability")
    print_key_value("Total gesture_eval rows", reliability["total_gesture_eval_rows"])
    print_key_value("Total labeled rows", reliability["total_labeled_rows"])
    print_key_value("Raw prediction accuracy", reliability["raw_prediction_accuracy"])
    print_key_value("Stable gesture accuracy", reliability["stable_gesture_accuracy"])
    print("Per-gesture counts:")
    if reliability["per_gesture_counts"]:
        for gesture_name, count in reliability["per_gesture_counts"].items():
            print(f"  {gesture_name}: {count}")
    else:
        print("  No labeled data")

    print_section("Safety")
    print_key_value("Total command_dispatch rows", safety["total_command_dispatch_rows"])
    print_key_value("Total command_blocked rows", safety["total_command_blocked_rows"])
    print_key_value("Command dispatch rate", safety["command_dispatch_rate"])
    print_key_value("Blocked command rate", safety["blocked_command_rate"])
    print_key_value("False command count", safety["false_command_count"])
    print_key_value("False command rate", safety["false_command_rate"])
    print("Blocked reasons breakdown:")
    if safety["blocked_reasons_breakdown"]:
        for reason, count in safety["blocked_reasons_breakdown"].items():
            print(f"  {reason}: {count}")
    else:
        print("  No blocked commands")

    print_section("Latency")
    print_key_value("Gesture ready count", latency["gesture_ready_count"])
    print_key_value("Command dispatch count", latency["command_dispatch_count"])
    print_key_value("Command blocked count", latency["command_blocked_count"])
    print_key_value("Motion observed count", latency["motion_observed_count"])
    print_key_value("Dominant delay stage", latency["dominant_delay_stage"])
    for metric_name in [
        "vision_to_stable_ms",
        "stable_to_dispatch_ms",
        "api_roundtrip_ms",
        "total_client_pipeline_ms",
    ]:
        metric = latency[metric_name]
        print_key_value(f"{metric_name} count", metric["count"])
        print_key_value(f"{metric_name} avg", metric["average"])
        print_key_value(f"{metric_name} median", metric["median"])
        print_key_value(f"{metric_name} min", metric["min"])
        print_key_value(f"{metric_name} max", metric["max"])
    api_latency = latency["api_latency_ms"]
    e2e_latency = latency["end_to_end_latency_ms"]
    print_key_value("API latency count", api_latency["count"])
    print_key_value("API latency avg", api_latency["average"])
    print_key_value("API latency median", api_latency["median"])
    print_key_value("API latency min", api_latency["min"])
    print_key_value("API latency max", api_latency["max"])
    print_key_value("E2E latency count", e2e_latency["count"])
    print_key_value("E2E latency avg", e2e_latency["average"])
    print_key_value("E2E latency median", e2e_latency["median"])
    print_key_value("E2E latency min", e2e_latency["min"])
    print_key_value("E2E latency max", e2e_latency["max"])

    print_section("Robustness")
    print_group_report("Lighting", robustness["lighting"])
    print_group_report("Background", robustness["background"])
    print_group_report("Distance", robustness["distance_m"])

    print_section("Confusion Matrix")
    confusion = reliability["confusion_matrix"]
    if isinstance(confusion, pd.DataFrame) and not confusion.empty:
        print(confusion.to_string())
    else:
        print("No labeled data")


def main(argv: list[str]) -> int:
    csv_path = resolve_csv_path(argv)
    dataframe = load_csv(csv_path)

    reliability = compute_reliability_metrics(dataframe)
    safety = compute_safety_metrics(dataframe)
    latency = compute_latency_metrics(dataframe)
    robustness = compute_robustness_metrics(dataframe)

    save_outputs(
        csv_path=csv_path,
        dataframe=dataframe,
        confusion=reliability["confusion_matrix"],
        reliability=reliability,
        safety=safety,
        latency=latency,
        robustness=robustness,
    )
    print_report(dataframe, reliability, safety, latency, robustness)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
