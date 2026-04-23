from __future__ import annotations

from pathlib import Path
from queue import Empty
from time import monotonic

from eodinga.common import WatchEvent
from eodinga.config import RootConfig
from eodinga.content.registry import parse
from eodinga.core.watcher import WatchService
from eodinga.index import open_index
from eodinga.index.build import rebuild_index
from eodinga.index.writer import IndexWriter
from eodinga.query import search
from tests.conftest import make_record


def _wait_for_query_hit(
    conn,
    service: WatchService,
    writer: IndexWriter,
    query: str,
    expected_path: Path,
    deadline_seconds: float,
) -> None:
    deadline = monotonic() + deadline_seconds
    while monotonic() < deadline:
        try:
            event = service.queue.get(timeout=0.05)
        except Empty:
            continue
        writer.apply_events([event], record_loader=make_record)
        hits = {hit.file.path for hit in search(conn, query, limit=5).hits}
        if expected_path in hits:
            return
    raise AssertionError(f"{expected_path} did not become query-visible within {deadline_seconds:.3f}s")


def test_watch_restart_clears_stale_pending_events_before_live_updates_resume(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    root.mkdir()
    rebuild_index(db_path, [RootConfig(path=root)], content_enabled=True)

    conn = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))

        stale = root / "stale.txt"
        service.record(
            WatchEvent(
                event_type="created",
                path=stale,
                root_path=root,
                happened_at=1.0,
            )
        )
        service.stop()

        service.start(root)
        fresh = root / "fresh.txt"
        fresh.write_text("fresh restart coverage\n", encoding="utf-8")

        _wait_for_query_hit(
            conn,
            service,
            writer,
            "fresh restart coverage",
            fresh,
            deadline_seconds=0.5,
        )

        stale_hits = [hit.file.path for hit in search(conn, "stale", limit=5).hits]
        fresh_hits = [hit.file.path for hit in search(conn, "fresh restart coverage", limit=5).hits]
    finally:
        service.stop()
        conn.close()

    assert stale_hits == []
    assert fresh_hits == [fresh]


def test_watch_restart_restarts_multi_root_scope_without_cross_root_leakage(tmp_path: Path) -> None:
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
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))

        service.start(root_a)
        service.start(root_b)
        service.stop()

        service.start(root_a)
        service.start(root_b)
        created = root_b / "beta-after-restart.txt"
        created.write_text("beta restart scoped visibility\n", encoding="utf-8")

        _wait_for_query_hit(
            conn,
            service,
            writer,
            "beta restart scoped visibility",
            created,
            deadline_seconds=0.5,
        )

        alpha_hits = {
            hit.file.path
            for hit in search(conn, "beta restart scoped visibility", limit=5, root=root_a).hits
        }
        beta_hits = {
            hit.file.path
            for hit in search(conn, "beta restart scoped visibility", limit=5, root=root_b).hits
        }
        all_hits = {hit.file.path for hit in search(conn, "beta restart scoped visibility", limit=5).hits}
    finally:
        service.stop()
        conn.close()

    assert alpha_hits == set()
    assert beta_hits == {created}
    assert all_hits == {created}
