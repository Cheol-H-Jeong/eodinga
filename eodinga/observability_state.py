from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TypedDict


class PersistedHistogram(TypedDict):
    bucket_hits: dict[str, int]
    buckets_ms: list[float]
    count: int
    max_ms: float | None
    min_ms: float | None
    sum_ms: float


class PersistedMetricsState(TypedDict):
    counters: dict[str, int]
    histograms: dict[str, PersistedHistogram]
    persisted_at: str
    recent_snapshots: list[dict[str, object]]
    version: int


def load_metrics_state(path: Path) -> PersistedMetricsState:
    if not path.exists():
        return _empty_state()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_state()
    if not isinstance(payload, dict):
        return _empty_state()
    return {
        "version": int(payload.get("version", 1)),
        "persisted_at": str(payload.get("persisted_at", "")),
        "counters": _coerce_counter_map(payload.get("counters")),
        "histograms": _coerce_histogram_map(payload.get("histograms")),
        "recent_snapshots": _coerce_snapshots(payload.get("recent_snapshots")),
    }


def merge_metrics_state(
    base_state: PersistedMetricsState,
    *,
    delta_counters: Mapping[str, int],
    delta_histograms: Mapping[str, PersistedHistogram],
    delta_snapshots: Sequence[dict[str, object]],
    snapshot_limit: int,
) -> PersistedMetricsState:
    counters = dict(base_state["counters"])
    for name, value in delta_counters.items():
        counters[name] = counters.get(name, 0) + value

    histograms = dict(base_state["histograms"])
    for name, histogram in delta_histograms.items():
        histograms[name] = _merge_histogram(histograms.get(name), histogram)

    snapshots = list(base_state["recent_snapshots"])
    snapshots.extend(dict(snapshot) for snapshot in delta_snapshots)
    if len(snapshots) > snapshot_limit:
        snapshots = snapshots[-snapshot_limit:]

    return {
        "version": 1,
        "persisted_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "counters": dict(sorted(counters.items())),
        "histograms": dict(sorted(histograms.items())),
        "recent_snapshots": snapshots,
    }


def write_metrics_state(path: Path, state: PersistedMetricsState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temp_path = Path(handle.name)
        json.dump(state, handle, sort_keys=True)
        handle.write("\n")
    temp_path.replace(path)


def _empty_state() -> PersistedMetricsState:
    return {
        "version": 1,
        "persisted_at": "",
        "counters": {},
        "histograms": {},
        "recent_snapshots": [],
    }


def _coerce_counter_map(value: object) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    counters: dict[str, int] = {}
    for key, item in value.items():
        if isinstance(key, str) and isinstance(item, int):
            counters[key] = item
    return counters


def _coerce_histogram_map(value: object) -> dict[str, PersistedHistogram]:
    if not isinstance(value, dict):
        return {}
    histograms: dict[str, PersistedHistogram] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, dict):
            continue
        histograms[key] = {
            "bucket_hits": _coerce_counter_map(item.get("bucket_hits")),
            "buckets_ms": [float(bucket) for bucket in item.get("buckets_ms", [])],
            "count": int(item.get("count", 0)),
            "sum_ms": float(item.get("sum_ms", 0.0)),
            "min_ms": _coerce_optional_float(item.get("min_ms")),
            "max_ms": _coerce_optional_float(item.get("max_ms")),
        }
    return histograms


def _coerce_optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _coerce_snapshots(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    snapshots: list[dict[str, object]] = []
    for item in value:
        if isinstance(item, dict):
            snapshots.append(dict(item))
    return snapshots


def _merge_histogram(
    base: PersistedHistogram | None,
    delta: PersistedHistogram,
) -> PersistedHistogram:
    if base is None or base["count"] <= 0:
        return {
            "bucket_hits": dict(sorted(delta["bucket_hits"].items())),
            "buckets_ms": list(delta["buckets_ms"]),
            "count": delta["count"],
            "sum_ms": delta["sum_ms"],
            "min_ms": delta["min_ms"],
            "max_ms": delta["max_ms"],
        }

    bucket_hits = dict(base["bucket_hits"])
    for label, value in delta["bucket_hits"].items():
        bucket_hits[label] = bucket_hits.get(label, 0) + value
    return {
        "bucket_hits": dict(sorted(bucket_hits.items())),
        "buckets_ms": list(base["buckets_ms"] or delta["buckets_ms"]),
        "count": base["count"] + delta["count"],
        "sum_ms": base["sum_ms"] + delta["sum_ms"],
        "min_ms": _merge_min(base["min_ms"], delta["min_ms"]),
        "max_ms": _merge_max(base["max_ms"], delta["max_ms"]),
    }


def _merge_min(left: float | None, right: float | None) -> float | None:
    if left is None:
        return right
    if right is None:
        return left
    return min(left, right)


def _merge_max(left: float | None, right: float | None) -> float | None:
    if left is None:
        return right
    if right is None:
        return left
    return max(left, right)
