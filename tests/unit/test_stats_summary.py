from __future__ import annotations

from eodinga.stats_summary import recent_snapshot_summary


def test_recent_snapshot_summary_counts_named_records_only() -> None:
    snapshots = [
        {"name": "command.search", "payload": {"query": "alpha"}},
        {"name": "command.search", "payload": {"query": "beta"}},
        {"name": "command.failure", "payload": {"command": "search"}},
        {"name": "", "payload": {}},
        {"payload": {"query": "missing-name"}},
        {"name": 3},
    ]

    assert recent_snapshot_summary(snapshots) == {
        "command.failure": 1,
        "command.search": 2,
    }
