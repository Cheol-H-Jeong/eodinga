from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from eodinga.__main__ import main
from eodinga.index.schema import apply_schema
from eodinga.observability import reset_metrics


def _build_search_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        apply_schema(conn)
        conn.execute(
            "INSERT INTO roots(id, path, include, exclude, added_at) VALUES (?, ?, ?, ?, ?)",
            (1, "/workspace", "[]", "[]", 1),
        )
        conn.execute(
            """
            INSERT INTO files (
              id, root_id, path, parent_path, name, name_lower, ext, size, mtime, ctime,
              is_dir, is_symlink, content_hash, indexed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                1,
                "/workspace/report.txt",
                "/workspace",
                "report.txt",
                "report.txt",
                "txt",
                1024,
                1_713_528_000,
                1_713_528_000,
                0,
                0,
                None,
                1_713_528_000,
            ),
        )
        conn.execute(
            "INSERT INTO content_fts(rowid, title, head_text, body_text) VALUES (?, ?, ?, ?)",
            (1, "report.txt", "alpha", "alpha launch note"),
        )
        conn.execute(
            """
            INSERT INTO content_map(file_id, fts_rowid, parser, parsed_at, content_sha)
            VALUES (?, ?, ?, ?, ?)
            """,
            (1, 1, "text", 1_713_528_000, b"sha-1"),
        )
        conn.commit()
    finally:
        conn.close()


def test_stats_json_loads_persisted_metrics_from_previous_command(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    db_path = tmp_path / "index.db"
    metrics_path = tmp_path / "runtime" / "metrics.json"
    _build_search_db(db_path)
    monkeypatch.setenv("EODINGA_METRICS_PATH", str(metrics_path))
    reset_metrics()

    search_exit = main(["--db", str(db_path), "search", "alpha", "--json"])
    search_output = capsys.readouterr()
    assert search_exit == 0
    assert json.loads(search_output.out)["count"] == 1
    assert metrics_path.exists()

    reset_metrics()

    stats_exit = main(["--db", str(db_path), "stats", "--json"])
    stats_output = capsys.readouterr()
    assert stats_exit == 0
    payload = json.loads(stats_output.out)
    assert payload["queries_served"] == 1
    assert payload["commands_started"] == 2
    assert payload["commands_completed"] == 1
    assert payload["metrics_path"] == str(metrics_path)
    assert payload["histograms"]["query_latency_ms"]["count"] == 1
    assert payload["histograms"]["command_latency_ms"]["count"] == 1
    assert payload["histograms"]["command_latency_ms.search"]["count"] == 1


def test_invalid_metrics_snapshot_does_not_break_cli(
    tmp_path: Path,
    monkeypatch,
) -> None:
    metrics_path = tmp_path / "runtime" / "metrics.json"
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text("{invalid json", encoding="utf-8")
    monkeypatch.setenv("EODINGA_METRICS_PATH", str(metrics_path))
    reset_metrics()

    exit_code = main(["version"])

    assert exit_code == 0


def test_stats_json_breaks_out_command_latency_by_command(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    db_path = tmp_path / "index.db"
    metrics_path = tmp_path / "runtime" / "metrics.json"
    _build_search_db(db_path)
    monkeypatch.setenv("EODINGA_METRICS_PATH", str(metrics_path))
    reset_metrics()

    search_exit = main(["--db", str(db_path), "search", "alpha", "--json"])
    search_output = capsys.readouterr()
    assert search_exit == 0
    assert json.loads(search_output.out)["count"] == 1

    stats_exit = main(["--db", str(db_path), "stats", "--json"])
    stats_output = capsys.readouterr()
    assert stats_exit == 0
    first_payload = json.loads(stats_output.out)
    assert first_payload["histograms"]["command_latency_ms"]["count"] == 1
    assert first_payload["histograms"]["command_latency_ms.search"]["count"] == 1
    assert "command_latency_ms.stats" not in first_payload["histograms"]

    second_stats_exit = main(["--db", str(db_path), "stats", "--json"])
    second_stats_output = capsys.readouterr()
    assert second_stats_exit == 0
    second_payload = json.loads(second_stats_output.out)
    assert second_payload["histograms"]["command_latency_ms"]["count"] == 2
    assert second_payload["histograms"]["command_latency_ms.search"]["count"] == 1
    assert second_payload["histograms"]["command_latency_ms.stats"]["count"] == 1
