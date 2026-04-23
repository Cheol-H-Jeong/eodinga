from __future__ import annotations

import json
from pathlib import Path

from eodinga.__main__ import main
from eodinga.observability import recent_snapshots, reset_metrics, snapshot_metrics


def _build_search_db(target: Path) -> None:
    docs = target.parent / "docs"
    docs.mkdir()
    (docs / "alpha.txt").write_text("alpha launch note\n", encoding="utf-8")
    (docs / "beta.txt").write_text("beta launch note\n", encoding="utf-8")
    exit_code = main(["--db", str(target), "index", "--root", str(docs), "--rebuild"])
    assert exit_code == 0


def test_record_snapshot_tracks_recorded_and_dropped_counts() -> None:
    reset_metrics()

    for index in range(25):
        from eodinga.observability import record_snapshot

        record_snapshot("command.search", {"index": index})

    metrics = snapshot_metrics()
    assert metrics["counters"]["snapshots_recorded"] == 25
    assert metrics["counters"]["snapshots.command.search"] == 25
    assert metrics["counters"]["snapshots_dropped"] == 5
    assert len(recent_snapshots()) == 20


def test_stats_json_exposes_snapshot_counters_and_activity(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "index.db"
    _build_search_db(db_path)
    capsys.readouterr()
    reset_metrics()

    assert main(["--db", str(db_path), "search", "launch", "--json"]) == 0
    capsys.readouterr()
    assert main(["--db", str(db_path), "version"]) == 0
    capsys.readouterr()

    stats_exit = main(["--db", str(db_path), "stats", "--json"])
    stats_output = capsys.readouterr()
    assert stats_exit == 0
    payload = json.loads(stats_output.out)
    assert payload["snapshots_recorded"] == 2
    assert payload["snapshots_dropped"] == 0
    assert payload["snapshot_activity"] == {
        "command.search": 1,
        "command.version": 1,
    }
    assert payload["counters"]["snapshots_recorded"] == 2
    assert payload["counters"]["snapshots.command.search"] == 1
    assert payload["counters"]["snapshots.command.version"] == 1
