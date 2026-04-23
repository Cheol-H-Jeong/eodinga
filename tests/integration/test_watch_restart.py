from __future__ import annotations

from pathlib import Path

from eodinga.config import RootConfig
from eodinga.content.registry import parse
from eodinga.core.watcher import WatchService
from eodinga.index import open_index
from eodinga.index.build import rebuild_index
from eodinga.index.writer import IndexWriter
from eodinga.query import search
from tests.integration._helpers import wait_for_query_hit


def test_watch_service_restart_after_stop_keeps_live_updates_visible(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"

    root.mkdir()
    (root / "existing.txt").write_text("watch restart survivor\n", encoding="utf-8")
    rebuild_index(db_path, [RootConfig(path=root)], content_enabled=True)

    conn = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root)
        service.stop()

        service.start(root)
        created = root / "after-restart.txt"
        created.write_text("watch restart live update\n", encoding="utf-8")
        elapsed = wait_for_query_hit(
            conn,
            service,
            writer,
            "watch restart live update",
            created,
            deadline_seconds=0.5,
        )
        existing_hits = {hit.file.path for hit in search(conn, "watch restart survivor", limit=10).hits}
        created_hits = {hit.file.path for hit in search(conn, "watch restart live update", limit=10).hits}
    finally:
        service.stop()
        conn.close()

    assert elapsed <= 0.5
    assert existing_hits == {root / "existing.txt"}
    assert created_hits == {created}


def test_watch_service_restart_after_stop_preserves_multi_root_scope(tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "database" / "index.db"

    root_a.mkdir()
    root_b.mkdir()
    (root_a / "alpha-existing.txt").write_text("watch restart alpha survivor\n", encoding="utf-8")
    rebuild_index(
        db_path,
        [RootConfig(path=root_a), RootConfig(path=root_b)],
        content_enabled=True,
    )

    conn = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root_a)
        service.start(root_b)
        service.stop()

        service.start(root_a)
        service.start(root_b)
        created = root_b / "beta-after-restart.txt"
        created.write_text("watch restart beta update\n", encoding="utf-8")
        elapsed = wait_for_query_hit(
            conn,
            service,
            writer,
            "watch restart beta update",
            created,
            deadline_seconds=0.5,
        )
        existing_hits = {
            hit.file.path for hit in search(conn, "watch restart alpha survivor", limit=10).hits
        }
        global_hits = {hit.file.path for hit in search(conn, "watch restart beta update", limit=10).hits}
        alpha_hits = {
            hit.file.path
            for hit in search(conn, "watch restart alpha survivor", limit=10, root=root_a).hits
        }
        beta_hits = {
            hit.file.path
            for hit in search(conn, "watch restart beta update", limit=10, root=root_b).hits
        }
    finally:
        service.stop()
        conn.close()

    assert elapsed <= 0.5
    assert existing_hits == {root_a / "alpha-existing.txt"}
    assert global_hits == {created}
    assert alpha_hits == {root_a / "alpha-existing.txt"}
    assert beta_hits == {created}
