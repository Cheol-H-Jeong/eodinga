from __future__ import annotations

from pathlib import Path

from eodinga.config import RootConfig
from eodinga.content.registry import parse
from eodinga.core.watcher import WatchService
from eodinga.index import open_index
from eodinga.index.build import rebuild_index
from eodinga.index.writer import IndexWriter
from eodinga.query import search
from tests.integration._helpers import wait_for_query_hit, wait_for_query_miss


def test_reopen_query_results_refresh_again_after_live_rewrite(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    root.mkdir()
    existing = root / "persisted.txt"
    target = root / "draft.txt"
    existing.write_text("persisted reopen baseline\n", encoding="utf-8")
    target.write_text("first reopen cycle marker\n", encoding="utf-8")
    rebuild_index(db_path, [RootConfig(path=root)], content_enabled=True)

    first_conn = open_index(db_path)
    try:
        baseline_hits = [hit.file.path for hit in search(first_conn, "persisted reopen baseline", limit=5).hits]
        first_cycle_hits = [hit.file.path for hit in search(first_conn, "first reopen cycle", limit=5).hits]
    finally:
        first_conn.close()

    reopened = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(reopened, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root)

        target.write_text("second reopen cycle marker\n", encoding="utf-8")

        appeared_elapsed = wait_for_query_hit(
            reopened,
            service,
            writer,
            "second reopen cycle",
            target,
            deadline_seconds=0.5,
        )
        removed_elapsed = wait_for_query_miss(
            reopened,
            service,
            writer,
            "first reopen cycle",
            target,
            deadline_seconds=0.5,
        )
        second_cycle_hits = [hit.file.path for hit in search(reopened, "second reopen cycle", limit=5).hits]
        stale_hits = [hit.file.path for hit in search(reopened, "first reopen cycle", limit=5).hits]
        baseline_hits_after_reopen = [
            hit.file.path for hit in search(reopened, "persisted reopen baseline", limit=5).hits
        ]
    finally:
        service.stop()
        reopened.close()

    assert baseline_hits == [existing]
    assert first_cycle_hits == [target]
    assert appeared_elapsed <= 0.5
    assert removed_elapsed <= 0.5
    assert second_cycle_hits == [target]
    assert stale_hits == []
    assert baseline_hits_after_reopen == [existing]
