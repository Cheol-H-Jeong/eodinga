from __future__ import annotations

from pathlib import Path

from eodinga.metrics_state import (
    current_metrics_state,
    load_metrics_state,
    merge_metrics_states,
    write_metrics_state,
)


def test_merge_metrics_states_combines_counters_histograms_and_recent_snapshots() -> None:
    persisted = current_metrics_state(
        generated_at="2026-04-23T00:00:00Z",
        counters={"queries_served": 2, "commands_started": 1},
        histograms={
            "query_latency_ms": {
                "count": 2,
                "sum_ms": 18.0,
                "min_ms": 7.0,
                "max_ms": 11.0,
                "buckets": {"<= 10ms": 1, "<= 25ms": 1},
            }
        },
        recent_snapshots=[
            {
                "name": "command.search",
                "recorded_at": "2026-04-23T00:00:00Z",
                "payload": {"query": "alpha"},
            }
        ],
    )
    current = current_metrics_state(
        generated_at="2026-04-23T00:01:00Z",
        counters={"queries_served": 1, "commands_started": 1},
        histograms={
            "query_latency_ms": {
                "count": 1,
                "sum_ms": 4.0,
                "min_ms": 4.0,
                "max_ms": 4.0,
                "buckets": {"<= 5ms": 1},
            }
        },
        recent_snapshots=[
            {
                "name": "command.stats",
                "recorded_at": "2026-04-23T00:01:00Z",
                "payload": {"queries_served": 3},
            }
        ],
    )

    merged = merge_metrics_states(persisted, current)

    assert merged["generated_at"] == "2026-04-23T00:01:00Z"
    assert merged["counters"] == {"commands_started": 2, "queries_served": 3}
    assert merged["histograms"]["query_latency_ms"] == {
        "count": 3,
        "sum_ms": 22.0,
        "min_ms": 4.0,
        "max_ms": 11.0,
        "buckets": {"<= 10ms": 1, "<= 25ms": 1, "<= 5ms": 1},
    }
    assert [entry["name"] for entry in merged["recent_snapshots"]] == [
        "command.search",
        "command.stats",
    ]


def test_write_metrics_state_is_atomic_and_loadable(tmp_path: Path) -> None:
    metrics_path = tmp_path / "state" / "metrics.json"
    state = current_metrics_state(
        generated_at="2026-04-23T00:00:00Z",
        counters={"queries_served": 1},
        histograms={},
        recent_snapshots=[],
    )

    write_metrics_state(metrics_path, state)

    assert metrics_path.exists()
    assert load_metrics_state(metrics_path) == state
    assert list(metrics_path.parent.glob(".*.tmp")) == []
