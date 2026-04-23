from __future__ import annotations

from pathlib import Path
from queue import Empty
from time import monotonic

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
) -> float:
    started = monotonic()
    deadline = started + deadline_seconds
    while monotonic() < deadline:
        try:
            event = service.queue.get(timeout=0.05)
        except Empty:
            continue
        writer.apply_events([event], record_loader=make_record)
        hits = [hit.file.path for hit in search(conn, query, limit=10).hits]
        if expected_path in hits:
            return monotonic() - started
    raise AssertionError(f"{expected_path} did not become query-visible within {deadline_seconds:.3f}s")


def _start_multi_root_watch(service: WatchService, *roots: Path) -> None:
    for root in roots:
        service.start(root)


def test_multi_root_live_update_preserves_secondary_root_identity_and_scope(
    tmp_path: Path,
) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "database" / "index.db"
    root_a.mkdir()
    root_b.mkdir()
    (root_a / "alpha.txt").write_text("alpha baseline document\n", encoding="utf-8")
    rebuild_index(
        db_path,
        [RootConfig(path=root_a), RootConfig(path=root_b)],
        content_enabled=True,
    )

    conn = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        _start_multi_root_watch(service, root_a, root_b)

        created = root_b / "beta-live.txt"
        created.write_text("beta live integration event\n", encoding="utf-8")
        _wait_for_query_hit(conn, service, writer, "beta live integration", created, 0.5)

        hits = {hit.file.path for hit in search(conn, "beta live integration", limit=10).hits}
        scoped_hits = {
            hit.file.path
            for hit in search(conn, "beta live integration", limit=10, root=root_b).hits
        }
        other_root_hits = {
            hit.file.path
            for hit in search(conn, "beta live integration", limit=10, root=root_a).hits
        }
        row = conn.execute(
            "SELECT root_id FROM files WHERE path = ?",
            (str(created),),
        ).fetchone()
    finally:
        service.stop()
        conn.close()

    assert hits == {created}
    assert scoped_hits == {created}
    assert other_root_hits == set()
    assert row is not None
    assert int(row[0]) == 2


def test_multi_root_rename_keeps_secondary_root_identity_after_watch_update(
    tmp_path: Path,
) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "database" / "index.db"
    root_a.mkdir()
    root_b.mkdir()
    source = root_b / "rename-source.txt"
    target = root_b / "rename-target.txt"
    source.write_text("rename flow stays scoped\n", encoding="utf-8")
    rebuild_index(
        db_path,
        [RootConfig(path=root_a), RootConfig(path=root_b)],
        content_enabled=True,
    )

    conn = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        _start_multi_root_watch(service, root_a, root_b)

        source.rename(target)
        _wait_for_query_hit(conn, service, writer, "rename flow stays scoped", target, 0.5)

        hits = {hit.file.path for hit in search(conn, "rename flow stays scoped", limit=10).hits}
        scoped_hits = {
            hit.file.path
            for hit in search(conn, "rename flow stays scoped", limit=10, root=root_b).hits
        }
        old_hits = {
            hit.file.path for hit in search(conn, "rename-source", limit=10, root=root_b).hits
        }
        rows = conn.execute(
            "SELECT path, root_id FROM files WHERE path IN (?, ?) ORDER BY path",
            (str(source), str(target)),
        ).fetchall()
    finally:
        service.stop()
        conn.close()

    assert hits == {target}
    assert scoped_hits == {target}
    assert old_hits == set()
    assert [(str(row[0]), int(row[1])) for row in rows] == [(str(target), 2)]
