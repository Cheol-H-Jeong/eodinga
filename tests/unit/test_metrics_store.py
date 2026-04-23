from __future__ import annotations

import json
from pathlib import Path

from eodinga.metrics_store import StoredMetrics, clear_metrics, empty_metrics, load_metrics, save_metrics


def test_load_metrics_returns_empty_when_missing(tmp_path: Path) -> None:
    assert load_metrics(tmp_path / "runtime-metrics.json") == empty_metrics()


def test_save_metrics_writes_atomic_json_payload(tmp_path: Path) -> None:
    path = tmp_path / "metrics" / "runtime.json"
    payload: StoredMetrics = {
        "counters": {"queries_served": 2},
        "histograms": {"query_latency_ms": {"count": 1}},
        "recent_snapshots": [{"name": "command.search"}],
    }

    save_metrics(path, payload)

    assert json.loads(path.read_text(encoding="utf-8")) == payload
    assert not (path.parent / "runtime.json.tmp").exists()


def test_load_metrics_quarantines_corrupt_payload(tmp_path: Path) -> None:
    path = tmp_path / "runtime-metrics.json"
    path.write_text("{not-json", encoding="utf-8")

    payload = load_metrics(path)

    assert payload == empty_metrics()
    assert not path.exists()
    quarantined = list(tmp_path.glob("runtime-metrics.corrupt-*.json"))
    assert len(quarantined) == 1


def test_clear_metrics_removes_store_file(tmp_path: Path) -> None:
    path = tmp_path / "runtime-metrics.json"
    save_metrics(path, empty_metrics())

    clear_metrics(path)

    assert not path.exists()
