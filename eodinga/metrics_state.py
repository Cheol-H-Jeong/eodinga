from __future__ import annotations

import json
import os
from collections import deque
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TypedDict

_SCHEMA_VERSION = 1
_RECENT_SNAPSHOT_LIMIT = 20


class PersistedMetricsState(TypedDict):
    schema_version: int
    generated_at: str
    counters: dict[str, int]
    histograms: dict[str, dict[str, object]]
    recent_snapshots: list[dict[str, object]]


def load_metrics_state(path: Path | None) -> PersistedMetricsState | None:
    if path is None or not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("metrics state payload must be an object")
    schema_version = int(payload.get("schema_version", 0))
    if schema_version != _SCHEMA_VERSION:
        raise ValueError(f"unsupported metrics state schema version: {schema_version}")
    counters = _coerce_counters(payload.get("counters", {}))
    histograms = _coerce_histograms(payload.get("histograms", {}))
    recent_snapshots = _coerce_recent_snapshots(payload.get("recent_snapshots", []))
    generated_at = str(payload.get("generated_at", ""))
    return {
        "schema_version": _SCHEMA_VERSION,
        "generated_at": generated_at,
        "counters": counters,
        "histograms": histograms,
        "recent_snapshots": recent_snapshots,
    }


def write_metrics_state(path: Path | None, state: PersistedMetricsState) -> Path | None:
    if path is None:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temp_path.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)
    return path


def merge_metrics_states(
    persisted: PersistedMetricsState | None,
    current: PersistedMetricsState,
) -> PersistedMetricsState:
    if persisted is None:
        return {
            "schema_version": _SCHEMA_VERSION,
            "generated_at": current["generated_at"],
            "counters": dict(sorted(current["counters"].items())),
            "histograms": dict(sorted(current["histograms"].items())),
            "recent_snapshots": list(current["recent_snapshots"]),
        }
    merged_counters = dict(persisted["counters"])
    for name, value in current["counters"].items():
        merged_counters[name] = merged_counters.get(name, 0) + value
    merged_histograms = dict(persisted["histograms"])
    for name, snapshot in current["histograms"].items():
        merged_histograms[name] = _merge_histogram_snapshot(merged_histograms.get(name), snapshot)
    merged_recent = deque[dict[str, object]](persisted["recent_snapshots"], maxlen=_RECENT_SNAPSHOT_LIMIT)
    merged_recent.extend(current["recent_snapshots"])
    return {
        "schema_version": _SCHEMA_VERSION,
        "generated_at": current["generated_at"],
        "counters": dict(sorted(merged_counters.items())),
        "histograms": dict(sorted(merged_histograms.items())),
        "recent_snapshots": list(merged_recent),
    }


def current_metrics_state(
    *,
    generated_at: str,
    counters: Mapping[str, int],
    histograms: Mapping[str, Mapping[str, object]],
    recent_snapshots: Sequence[Mapping[str, object]],
) -> PersistedMetricsState:
    return {
        "schema_version": _SCHEMA_VERSION,
        "generated_at": generated_at,
        "counters": dict(sorted((str(name), int(value)) for name, value in counters.items())),
        "histograms": _coerce_histograms(histograms),
        "recent_snapshots": _coerce_recent_snapshots(recent_snapshots),
    }


def _coerce_counters(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise ValueError("metrics counters payload must be an object")
    return dict(sorted((str(name), int(counter)) for name, counter in value.items()))


def _coerce_histograms(value: object) -> dict[str, dict[str, object]]:
    if not isinstance(value, Mapping):
        raise ValueError("metrics histograms payload must be an object")
    histograms: dict[str, dict[str, object]] = {}
    for name, payload in value.items():
        if not isinstance(payload, Mapping):
            raise ValueError(f"histogram {name!r} payload must be an object")
        histogram = {
            "count": _int_value(payload.get("count", 0)),
            "sum_ms": round(_float_value(payload.get("sum_ms", 0.0)), 3),
            "min_ms": round(_float_value(payload.get("min_ms", 0.0)), 3),
            "max_ms": round(_float_value(payload.get("max_ms", 0.0)), 3),
            "buckets": _coerce_histogram_buckets(payload.get("buckets", {})),
        }
        histograms[str(name)] = histogram
    return dict(sorted(histograms.items()))


def _coerce_histogram_buckets(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise ValueError("histogram buckets payload must be an object")
    return dict(sorted((str(name), int(count)) for name, count in value.items()))


def _coerce_recent_snapshots(value: object) -> list[dict[str, object]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError("recent snapshots payload must be a list")
    snapshots: deque[dict[str, object]] = deque(maxlen=_RECENT_SNAPSHOT_LIMIT)
    for entry in value:
        if not isinstance(entry, Mapping):
            raise ValueError("snapshot entry must be an object")
        snapshots.append(dict(entry))
    return list(snapshots)


def _merge_histogram_snapshot(
    persisted: dict[str, object] | None,
    current: Mapping[str, object],
) -> dict[str, object]:
    if persisted is None:
        return {
            "count": _int_value(current.get("count", 0)),
            "sum_ms": round(_float_value(current.get("sum_ms", 0.0)), 3),
            "min_ms": round(_float_value(current.get("min_ms", 0.0)), 3),
            "max_ms": round(_float_value(current.get("max_ms", 0.0)), 3),
            "buckets": _coerce_histogram_buckets(current.get("buckets", {})),
        }
    persisted_count = _int_value(persisted.get("count", 0))
    current_count = _int_value(current.get("count", 0))
    merged_count = persisted_count + current_count
    merged_min = _merge_histogram_min(
        persisted.get("min_ms"),
        current.get("min_ms"),
        persisted_count=persisted_count,
        current_count=current_count,
    )
    merged_max = _merge_histogram_max(
        persisted.get("max_ms"),
        current.get("max_ms"),
        persisted_count=persisted_count,
        current_count=current_count,
    )
    buckets = _coerce_histogram_buckets(persisted.get("buckets", {}))
    for label, count in _coerce_histogram_buckets(current.get("buckets", {})).items():
        buckets[label] = buckets.get(label, 0) + count
    return {
        "count": merged_count,
        "sum_ms": round(
            _float_value(persisted.get("sum_ms", 0.0)) + _float_value(current.get("sum_ms", 0.0)),
            3,
        ),
        "min_ms": round(merged_min, 3),
        "max_ms": round(merged_max, 3),
        "buckets": dict(sorted(buckets.items())),
    }


def _merge_histogram_min(
    persisted_min: object,
    current_min: object,
    *,
    persisted_count: int,
    current_count: int,
) -> float:
    if persisted_count <= 0:
        return _float_value(current_min)
    if current_count <= 0:
        return _float_value(persisted_min)
    return min(_float_value(persisted_min), _float_value(current_min))


def _merge_histogram_max(
    persisted_max: object,
    current_max: object,
    *,
    persisted_count: int,
    current_count: int,
) -> float:
    if persisted_count <= 0:
        return _float_value(current_max)
    if current_count <= 0:
        return _float_value(persisted_max)
    return max(_float_value(persisted_max), _float_value(current_max))


def _int_value(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        return int(value)
    raise ValueError(f"unsupported integer value: {value!r}")


def _float_value(value: object) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(value)
    if value is None:
        return 0.0
    raise ValueError(f"unsupported float value: {value!r}")
