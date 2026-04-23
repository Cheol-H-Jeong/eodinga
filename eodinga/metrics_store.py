from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict


class StoredMetrics(TypedDict):
    counters: dict[str, int]
    histograms: dict[str, dict[str, object]]
    recent_snapshots: list[dict[str, object]]


def empty_metrics() -> StoredMetrics:
    return {"counters": {}, "histograms": {}, "recent_snapshots": []}


def load_metrics(path: Path) -> StoredMetrics:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return empty_metrics()
    except (OSError, json.JSONDecodeError):
        quarantine_metrics(path)
        return empty_metrics()
    if not isinstance(payload, dict):
        quarantine_metrics(path)
        return empty_metrics()
    counters = payload.get("counters", {})
    histograms = payload.get("histograms", {})
    recent_snapshots = payload.get("recent_snapshots", [])
    return {
        "counters": counters if isinstance(counters, dict) else {},
        "histograms": histograms if isinstance(histograms, dict) else {},
        "recent_snapshots": recent_snapshots if isinstance(recent_snapshots, list) else [],
    }


def save_metrics(path: Path, payload: StoredMetrics) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    target = path.with_name(f"{path.name}.tmp")
    target.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    target.replace(path)


def clear_metrics(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return


def quarantine_metrics(path: Path) -> Path | None:
    try:
        suffix = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
        target = path.with_name(f"{path.stem}.corrupt-{suffix}{path.suffix}")
        path.replace(target)
    except OSError:
        return None
    return target
