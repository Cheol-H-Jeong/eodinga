from __future__ import annotations

from pathlib import Path

from eodinga.config import RootConfig
from eodinga.content.registry import parse
from eodinga.core.watcher import WatchService
from eodinga.index import open_index
from eodinga.index.build import rebuild_index
from eodinga.index.writer import IndexWriter
from tests.integration._helpers import run_cli_json, wait_for_query_hit


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


def test_cli_search_sees_live_update_after_watch_apply(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    root.mkdir()
    rebuild_index(db_path, [RootConfig(path=root)], content_enabled=True)

    conn = open_index(db_path)
    service = WatchService()
    elapsed = 0.0
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root)

        created = root / "after-watch.txt"
        created.write_text("cli watch integration marker\n", encoding="utf-8")
        elapsed = wait_for_query_hit(
            conn,
            service,
            writer,
            "cli watch integration marker",
            created,
            deadline_seconds=0.5,
        )
    finally:
        service.stop()
        conn.close()

    search_exit, search_payload, search_stderr = run_cli_json(
        ["--db", str(db_path), "search", "cli watch integration marker", "--json"]
    )

    assert elapsed <= 0.5
    assert search_exit == 0
    assert search_stderr == ""
    assert search_payload["count"] == 1
    assert search_payload["returned"] == 1
    assert [result["path"] for result in search_payload["results"]] == [str(created)]


def test_cli_search_preserves_multi_root_scope_after_live_update(tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "database" / "index.db"
    root_a.mkdir()
    root_b.mkdir()
    rebuild_index(
        db_path,
        [RootConfig(path=root_a), RootConfig(path=root_b)],
        content_enabled=True,
    )

    conn = open_index(db_path)
    service = WatchService()
    elapsed = 0.0
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root_a)
        service.start(root_b)

        created = root_b / "beta-after-watch.txt"
        created.write_text("cli scoped watch marker\n", encoding="utf-8")
        elapsed = wait_for_query_hit(
            conn,
            service,
            writer,
            "cli scoped watch marker",
            created,
            deadline_seconds=0.5,
        )
    finally:
        service.stop()
        conn.close()

    global_exit, global_payload, global_stderr = run_cli_json(
        ["--db", str(db_path), "search", "cli scoped watch marker", "--json"]
    )
    alpha_exit, alpha_payload, alpha_stderr = run_cli_json(
        [
            "--db",
            str(db_path),
            "search",
            "cli scoped watch marker",
            "--json",
            "--root",
            str(root_a),
        ]
    )
    beta_exit, beta_payload, beta_stderr = run_cli_json(
        [
            "--db",
            str(db_path),
            "search",
            "cli scoped watch marker",
            "--json",
            "--root",
            str(root_b),
        ]
    )

    assert elapsed <= 0.5
    assert global_exit == 0
    assert global_stderr == ""
    assert [result["path"] for result in global_payload["results"]] == [str(created)]
    assert alpha_exit == 0
    assert alpha_stderr == ""
    assert alpha_payload["count"] == 0
    assert alpha_payload["returned"] == 0
    assert alpha_payload["results"] == []
    assert beta_exit == 0
    assert beta_stderr == ""
    assert beta_payload["count"] == 1
    assert beta_payload["returned"] == 1
    assert [result["path"] for result in beta_payload["results"]] == [str(created)]
