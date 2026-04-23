from __future__ import annotations

import os
from json import dumps as json_dumps
from json import loads as json_loads
from pathlib import Path
from typing import Callable, TypedDict


class SnapshotRecord(TypedDict):
    name: str
    recorded_at: str
    payload: dict[str, object]


class MetricsStateSnapshot(TypedDict):
    counters: dict[str, int]
    histograms: dict[str, dict[str, object]]
    persistence_enabled: bool
    metrics_path: str | None
    recent_snapshots: list[SnapshotRecord]


class PersistedMetricsState(TypedDict):
    counters: dict[str, int]
    histograms: dict[str, dict[str, object]]
    recent_snapshots: list[SnapshotRecord]


def default_metrics_path(default_state_dir: Callable[[], Path]) -> Path:
    return default_state_dir() / "metrics.json"


def resolve_metrics_path(
    default_state_dir: Callable[[], Path],
    metrics_path: Path | None = None,
) -> Path | None:
    if os.environ.get("EODINGA_DISABLE_METRICS_PERSISTENCE") == "1":
        return None
    if metrics_path is not None:
        return metrics_path.expanduser()
    override_path = os.environ.get("EODINGA_METRICS_PATH")
    if override_path:
        return Path(override_path).expanduser()
    if "PYTEST_CURRENT_TEST" in os.environ:
        return None
    return default_metrics_path(default_state_dir)


def snapshot_metrics_state(
    *,
    default_state_dir: Callable[[], Path],
    runtime_counters: dict[str, int],
    runtime_histograms: dict[str, dict[str, object]],
    runtime_snapshots: list[SnapshotRecord],
) -> MetricsStateSnapshot:
    metrics_path = resolve_metrics_path(default_state_dir)
    if metrics_path is None:
        return {
            "counters": dict(sorted(runtime_counters.items())),
            "histograms": dict(sorted(runtime_histograms.items())),
            "persistence_enabled": False,
            "metrics_path": None,
            "recent_snapshots": list(runtime_snapshots),
        }
    state = _read_metrics_state(metrics_path)
    return {
        "counters": dict(sorted(state["counters"].items())),
        "histograms": dict(sorted(state["histograms"].items())),
        "persistence_enabled": True,
        "metrics_path": str(metrics_path),
        "recent_snapshots": list(state["recent_snapshots"]),
    }


def reset_persisted_metrics(default_state_dir: Callable[[], Path]) -> None:
    metrics_path = resolve_metrics_path(default_state_dir)
    if metrics_path is None:
        return
    _write_metrics_state(metrics_path, _empty_metrics_state())


def persist_metric_update(
    *,
    default_state_dir: Callable[[], Path],
    recent_snapshot_limit: int,
    counter_updates: dict[str, int] | None = None,
    histogram_updates: tuple[tuple[str, float, tuple[float, ...]], ...] = (),
    snapshot_record: SnapshotRecord | None = None,
) -> None:
    metrics_path = resolve_metrics_path(default_state_dir)
    if metrics_path is None:
        return
    state = _read_metrics_state(metrics_path)
    if counter_updates is not None:
        for name, value in counter_updates.items():
            state["counters"][name] = state["counters"].get(name, 0) + value
    for name, value_ms, buckets_ms in histogram_updates:
        histogram = state["histograms"].get(name)
        if histogram is None:
            histogram = {
                "count": 0,
                "sum_ms": 0.0,
                "min_ms": 0.0,
                "max_ms": 0.0,
                "buckets": {},
            }
            state["histograms"][name] = histogram
        _observe_histogram_snapshot(histogram, value_ms, buckets_ms)
    if snapshot_record is not None:
        state["recent_snapshots"].append(snapshot_record)
        del state["recent_snapshots"][:-recent_snapshot_limit]
    _write_metrics_state(metrics_path, state)


def _empty_metrics_state() -> PersistedMetricsState:
    return {"counters": {}, "histograms": {}, "recent_snapshots": []}


def _read_metrics_state(metrics_path: Path) -> PersistedMetricsState:
    try:
        raw = json_loads(metrics_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _empty_metrics_state()
    counters = raw.get("counters", {}) if isinstance(raw, dict) else {}
    histograms = raw.get("histograms", {}) if isinstance(raw, dict) else {}
    snapshots = raw.get("recent_snapshots", []) if isinstance(raw, dict) else []
    return {
        "counters": _coerce_counter_map(counters),
        "histograms": _coerce_histogram_map(histograms),
        "recent_snapshots": _coerce_snapshot_records(snapshots),
    }


def _write_metrics_state(metrics_path: Path, state: PersistedMetricsState) -> None:
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = metrics_path.with_suffix(f"{metrics_path.suffix}.tmp")
    tmp_path.write_text(json_dumps(state, sort_keys=True), encoding="utf-8")
    tmp_path.replace(metrics_path)


def _observe_histogram_snapshot(
    histogram: dict[str, object],
    value_ms: float,
    buckets_ms: tuple[float, ...],
) -> None:
    histogram["count"] = _coerce_int(histogram.get("count")) + 1
    histogram["sum_ms"] = round(_coerce_float(histogram.get("sum_ms")) + value_ms, 3)
    current_min = _coerce_optional_float(histogram.get("min_ms"))
    current_max = _coerce_optional_float(histogram.get("max_ms"))
    histogram["min_ms"] = round(
        value_ms if current_min is None else min(current_min, value_ms),
        3,
    )
    histogram["max_ms"] = round(
        value_ms if current_max is None else max(current_max, value_ms),
        3,
    )
    buckets = histogram.get("buckets")
    if not isinstance(buckets, dict):
        buckets = {}
        histogram["buckets"] = buckets
    label = _bucket_label(value_ms, buckets_ms)
    buckets[label] = _coerce_int(buckets.get(label)) + 1


def _coerce_int(value: object) -> int:
    return value if isinstance(value, int) else 0


def _coerce_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _coerce_optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _bucket_label(value_ms: float, buckets_ms: tuple[float, ...]) -> str:
    for upper_bound in buckets_ms:
        if value_ms <= upper_bound:
            return f"<= {upper_bound:g}ms"
    return f"> {buckets_ms[-1]:g}ms"


def _coerce_counter_map(raw: object) -> dict[str, int]:
    if not isinstance(raw, dict):
        return {}
    counters: dict[str, int] = {}
    for key, value in raw.items():
        if isinstance(key, str) and isinstance(value, int):
            counters[key] = value
    return counters


def _coerce_histogram_map(raw: object) -> dict[str, dict[str, object]]:
    if not isinstance(raw, dict):
        return {}
    histograms: dict[str, dict[str, object]] = {}
    for key, value in raw.items():
        if isinstance(key, str) and isinstance(value, dict):
            histogram: dict[str, object] = {}
            for item_key, item_value in value.items():
                if isinstance(item_key, str):
                    histogram[item_key] = item_value
            histograms[key] = histogram
    return histograms


def _coerce_snapshot_records(raw: object) -> list[SnapshotRecord]:
    if not isinstance(raw, list):
        return []
    snapshots: list[SnapshotRecord] = []
    for value in raw:
        if not isinstance(value, dict):
            continue
        name = value.get("name")
        recorded_at = value.get("recorded_at")
        payload = value.get("payload")
        if isinstance(name, str) and isinstance(recorded_at, str) and isinstance(payload, dict):
            payload_dict: dict[str, object] = {}
            for item_key, item_value in payload.items():
                if isinstance(item_key, str):
                    payload_dict[item_key] = item_value
            snapshots.append(
                {
                    "name": name,
                    "recorded_at": recorded_at,
                    "payload": payload_dict,
                }
            )
    return snapshots
