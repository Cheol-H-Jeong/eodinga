from __future__ import annotations

import json
from pathlib import Path


def test_cli_roundtrip_index_search_and_stats_across_processes(cli_runner, tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "database" / "index.db"
    root_a.mkdir()
    root_b.mkdir()
    (root_a / "alpha-launch.txt").write_text("alpha launch roundtrip\n", encoding="utf-8")
    (root_b / "beta-launch.txt").write_text("beta launch roundtrip\n", encoding="utf-8")
    (root_b / "beta-only.txt").write_text("beta scoped result\n", encoding="utf-8")

    index_result = cli_runner(
        "--db",
        str(db_path),
        "index",
        "--rebuild",
        "--root",
        str(root_a),
        "--root",
        str(root_b),
    )
    assert index_result.returncode == 0
    index_payload = json.loads(index_result.stdout)
    assert index_payload["files_indexed"] == 5
    assert index_payload["roots"] == [str(root_a), str(root_b)]

    search_result = cli_runner("--db", str(db_path), "search", "launch roundtrip", "--json")
    assert search_result.returncode == 0
    search_payload = json.loads(search_result.stdout)
    assert {Path(item["path"]).name for item in search_payload["results"]} == {
        "alpha-launch.txt",
        "beta-launch.txt",
    }

    scoped_result = cli_runner(
        "--db",
        str(db_path),
        "search",
        "scoped result",
        "--json",
        "--root",
        str(root_b),
    )
    assert scoped_result.returncode == 0
    scoped_payload = json.loads(scoped_result.stdout)
    assert [Path(item["path"]).name for item in scoped_payload["results"]] == ["beta-only.txt"]

    stats_result = cli_runner("--db", str(db_path), "stats", "--json")
    assert stats_result.returncode == 0
    stats_payload = json.loads(stats_result.stdout)
    assert stats_payload["files_indexed"] == 5
    assert set(stats_payload["roots"]) == {str(root_a), str(root_b)}
