from __future__ import annotations

import json
from pathlib import Path

from eodinga.__main__ import main
from eodinga.observability import reset_metrics


def _read_json(capsys) -> dict[str, object]:
    captured = capsys.readouterr()
    assert captured.err == ""
    return json.loads(captured.out)


def test_cli_flow_indexes_searches_and_reports_stats(tmp_path: Path, capsys) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "index.db"
    root.mkdir()
    (root / "launch-plan.txt").write_text("launch flow integration\n", encoding="utf-8")
    (root / "retro.txt").write_text("retro only\n", encoding="utf-8")
    reset_metrics()

    assert main(["--db", str(db_path), "index", "--root", str(root), "--rebuild"]) == 0
    index_payload = _read_json(capsys)

    assert main(["--db", str(db_path), "search", "launch flow", "--json"]) == 0
    search_payload = _read_json(capsys)

    assert main(["--db", str(db_path), "stats", "--json"]) == 0
    stats_payload = _read_json(capsys)

    assert index_payload["command"] == "index"
    assert index_payload["files_indexed"] >= 2
    assert [Path(item["path"]).name for item in search_payload["results"]] == ["launch-plan.txt"]
    assert search_payload["count"] == 1
    assert stats_payload["files_indexed"] == 3
    assert stats_payload["documents_indexed"] == 2
    assert stats_payload["queries_served"] == 1
    assert stats_payload["commands"]["index"]["completed"] == 1
    assert stats_payload["commands"]["search"]["completed"] == 1


def test_cli_flow_multi_root_search_respects_root_scope(tmp_path: Path, capsys) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "index.db"
    root_a.mkdir()
    root_b.mkdir()
    (root_a / "alpha-note.txt").write_text("shared multi root phrase\n", encoding="utf-8")
    (root_b / "beta-note.txt").write_text("shared multi root phrase\n", encoding="utf-8")
    reset_metrics()

    assert (
        main(
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
        == 0
    )
    _read_json(capsys)

    assert main(["--db", str(db_path), "search", "shared multi root phrase", "--json"]) == 0
    global_payload = _read_json(capsys)

    assert (
        main(
            [
                "--db",
                str(db_path),
                "search",
                "shared multi root phrase",
                "--json",
                "--root",
                str(root_b),
            ]
        )
        == 0
    )
    beta_payload = _read_json(capsys)

    assert {Path(item["path"]).name for item in global_payload["results"]} == {
        "alpha-note.txt",
        "beta-note.txt",
    }
    assert [Path(item["path"]).name for item in beta_payload["results"]] == ["beta-note.txt"]


def test_cli_flow_rebuild_with_trimmed_roots_drops_removed_scope(tmp_path: Path, capsys) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "index.db"
    root_a.mkdir()
    root_b.mkdir()
    (root_a / "alpha-survivor.txt").write_text("trimmed scope phrase\n", encoding="utf-8")
    (root_b / "beta-pruned.txt").write_text("trimmed scope phrase\n", encoding="utf-8")
    reset_metrics()

    assert (
        main(
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
        == 0
    )
    _read_json(capsys)

    assert main(["--db", str(db_path), "index", "--root", str(root_a), "--rebuild"]) == 0
    _read_json(capsys)

    assert main(["--db", str(db_path), "search", "trimmed scope phrase", "--json"]) == 0
    global_payload = _read_json(capsys)

    assert (
        main(
            [
                "--db",
                str(db_path),
                "search",
                "trimmed scope phrase",
                "--json",
                "--root",
                str(root_b),
            ]
        )
        == 0
    )
    beta_payload = _read_json(capsys)

    assert [Path(item["path"]).name for item in global_payload["results"]] == ["alpha-survivor.txt"]
    assert beta_payload["results"] == []
