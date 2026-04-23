from __future__ import annotations

from pathlib import Path

from tests.integration._helpers import run_cli_json


def test_cli_index_then_search_returns_indexed_hit(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    root.mkdir()
    target = root / "launch-note.txt"
    target.write_text("cli end to end launch marker\n", encoding="utf-8")

    index_exit, index_payload, index_stderr = run_cli_json(
        ["--db", str(db_path), "index", "--root", str(root), "--rebuild"]
    )
    search_exit, search_payload, search_stderr = run_cli_json(
        ["--db", str(db_path), "search", "launch marker", "--json"]
    )

    assert index_exit == 0
    assert index_stderr == ""
    assert index_payload["command"] == "index"
    assert index_payload["db"] == str(db_path)
    assert index_payload["roots"] == [str(root)]
    assert index_payload["files_indexed"] >= 1

    assert search_exit == 0
    assert search_stderr == ""
    assert search_payload["query"] == "launch marker"
    assert search_payload["count"] == 1
    assert search_payload["returned"] == 1
    assert [result["path"] for result in search_payload["results"]] == [str(target)]


def test_cli_search_root_scope_isolated_across_multi_root_index(tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "database" / "index.db"
    root_a.mkdir()
    root_b.mkdir()
    alpha = root_a / "alpha-launch.txt"
    beta = root_b / "beta-launch.txt"
    alpha.write_text("cli shared launch marker\n", encoding="utf-8")
    beta.write_text("cli shared launch marker\n", encoding="utf-8")

    index_exit, _, index_stderr = run_cli_json(
        [
            "--db",
            str(db_path),
            "index",
            "--root",
            str(root_a),
            "--root",
            str(root_b),
            "--rebuild",
        ]
    )
    search_exit, search_payload, search_stderr = run_cli_json(
        ["--db", str(db_path), "search", "launch marker", "--json", "--root", str(root_b)]
    )

    assert index_exit == 0
    assert index_stderr == ""
    assert search_exit == 0
    assert search_stderr == ""
    assert search_payload["count"] == 1
    assert search_payload["returned"] == 1
    assert [result["path"] for result in search_payload["results"]] == [str(beta)]
