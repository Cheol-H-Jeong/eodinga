from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MetricsState:
    counters: dict[str, int]
    histograms: dict[str, dict[str, object]]
    recent_snapshots: list[dict[str, object]]


def load_metrics_state(path: Path) -> MetricsState:
    payload = json.loads(path.read_text(encoding="utf-8"))
    counters = _normalize_counters(payload.get("counters"))
    histograms = _normalize_histograms(payload.get("histograms"))
    recent_snapshots = _normalize_recent_snapshots(payload.get("recent_snapshots"))
    return MetricsState(
        counters=counters,
        histograms=histograms,
        recent_snapshots=recent_snapshots,
    )


def save_metrics_state(
    path: Path,
    *,
    counters: dict[str, int],
    histograms: dict[str, dict[str, object]],
    recent_snapshots: list[dict[str, object]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "counters": counters,
        "histograms": histograms,
        "recent_snapshots": recent_snapshots,
    }
    temp_path = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temp_path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    os.replace(temp_path, path)


def delete_metrics_state(path: Path) -> None:
    path.unlink(missing_ok=True)


def _normalize_counters(value: object) -> dict[str, int]:
    if not isinstance(value, dict):
        raise ValueError("metrics store counters payload is invalid")
    normalized: dict[str, int] = {}
    for name, raw_count in value.items():
        if not isinstance(name, str) or not isinstance(raw_count, int):
            raise ValueError("metrics store counters payload is invalid")
        normalized[name] = raw_count
    return normalized


def _normalize_histograms(value: object) -> dict[str, dict[str, object]]:
    if not isinstance(value, dict):
        raise ValueError("metrics store histograms payload is invalid")
    normalized: dict[str, dict[str, object]] = {}
    for name, snapshot in value.items():
        if not isinstance(name, str) or not isinstance(snapshot, dict):
            raise ValueError("metrics store histograms payload is invalid")
        bounds = snapshot.get("bounds_ms")
        buckets = snapshot.get("buckets")
        if not isinstance(bounds, list) or not all(isinstance(item, (int, float)) for item in bounds):
            raise ValueError("metrics store histogram bounds are invalid")
        if not isinstance(buckets, dict) or not all(
            isinstance(label, str) and isinstance(count, int) for label, count in buckets.items()
        ):
            raise ValueError("metrics store histogram buckets are invalid")
        count = snapshot.get("count")
        sum_ms = snapshot.get("sum_ms")
        min_ms = snapshot.get("min_ms")
        max_ms = snapshot.get("max_ms")
        if not isinstance(count, int) or not isinstance(sum_ms, (int, float)):
            raise ValueError("metrics store histogram summary is invalid")
        if min_ms is not None and not isinstance(min_ms, (int, float)):
            raise ValueError("metrics store histogram summary is invalid")
        if max_ms is not None and not isinstance(max_ms, (int, float)):
            raise ValueError("metrics store histogram summary is invalid")
        normalized[name] = {
            "count": count,
            "sum_ms": float(sum_ms),
            "min_ms": None if min_ms is None else float(min_ms),
            "max_ms": None if max_ms is None else float(max_ms),
            "buckets": dict(sorted(buckets.items())),
            "bounds_ms": [float(item) for item in bounds],
        }
    return normalized


def _normalize_recent_snapshots(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise ValueError("metrics store recent snapshots payload is invalid")
    normalized: list[dict[str, object]] = []
    for entry in value:
        if not isinstance(entry, dict):
            raise ValueError("metrics store recent snapshots payload is invalid")
        name = entry.get("name")
        recorded_at = entry.get("recorded_at")
        payload = entry.get("payload")
        if not isinstance(name, str) or not isinstance(recorded_at, str) or not isinstance(payload, dict):
            raise ValueError("metrics store recent snapshots payload is invalid")
        normalized.append(
            {
                "name": name,
                "recorded_at": recorded_at,
                "payload": _normalize_json_mapping(payload),
            }
        )
    return normalized


def _normalize_json_mapping(value: dict[str, Any]) -> dict[str, object]:
    normalized: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError("metrics store snapshot payload is invalid")
        normalized[key] = _normalize_json_value(item)
    return normalized


def _normalize_json_value(value: Any) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_normalize_json_value(item) for item in value]
    if isinstance(value, dict):
        return _normalize_json_mapping(value)
    raise ValueError("metrics store snapshot payload is invalid")
