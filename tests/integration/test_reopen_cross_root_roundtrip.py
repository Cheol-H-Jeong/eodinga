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


def test_reopen_cross_root_move_then_rewrite_keeps_scope_and_fresh_content(tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "database" / "index.db"
    root_a.mkdir()
    root_b.mkdir()
    source = root_a / "draft.txt"
    source.write_text("cross root reopen original\n", encoding="utf-8")
    rebuild_index(
        db_path,
        [RootConfig(path=root_a), RootConfig(path=root_b)],
        content_enabled=True,
    )

    first_conn = open_index(db_path)
    try:
        initial_global_hits = {
            hit.file.path for hit in search(first_conn, "cross root reopen original", limit=5).hits
        }
        initial_alpha_hits = {
            hit.file.path
            for hit in search(first_conn, "cross root reopen original", limit=5, root=root_a).hits
        }
    finally:
        first_conn.close()

    reopened = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(reopened, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root_a)
        service.start(root_b)

        destination = root_b / "draft.txt"
        source.rename(destination)

        moved_elapsed = wait_for_query_hit(
            reopened,
            service,
            writer,
            "cross root reopen original",
            destination,
            deadline_seconds=0.5,
        )
        removed_elapsed = wait_for_query_miss(
            reopened,
            service,
            writer,
            "cross root reopen original",
            source,
            deadline_seconds=0.5,
        )

        destination.write_text("cross root reopen rewritten\n", encoding="utf-8")

        rewritten_elapsed = wait_for_query_hit(
            reopened,
            service,
            writer,
            "cross root reopen rewritten",
            destination,
            deadline_seconds=0.5,
        )
        stale_after_rewrite_elapsed = wait_for_query_miss(
            reopened,
            service,
            writer,
            "cross root reopen original",
            destination,
            deadline_seconds=0.5,
        )
        alpha_hits = {
            hit.file.path
            for hit in search(reopened, "cross root reopen rewritten", limit=5, root=root_a).hits
        }
        beta_hits = {
            hit.file.path
            for hit in search(reopened, "cross root reopen rewritten", limit=5, root=root_b).hits
        }
        stale_hits = {hit.file.path for hit in search(reopened, "cross root reopen original", limit=5).hits}
        fresh_hits = {hit.file.path for hit in search(reopened, "cross root reopen rewritten", limit=5).hits}
    finally:
        service.stop()
        reopened.close()

    assert initial_global_hits == {source}
    assert initial_alpha_hits == {source}
    assert moved_elapsed <= 0.5
    assert removed_elapsed <= 0.5
    assert rewritten_elapsed <= 0.5
    assert stale_after_rewrite_elapsed <= 0.5
    assert alpha_hits == set()
    assert beta_hits == {destination}
    assert stale_hits == set()
    assert fresh_hits == {destination}
