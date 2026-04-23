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


def _wait_for(
    conn,
    service: WatchService,
    writer: IndexWriter,
    predicate,
    *,
    deadline_seconds: float,
    failure_message: str,
) -> float:
    started = monotonic()
    deadline = started + deadline_seconds
    while monotonic() < deadline:
        try:
            event = service.queue.get(timeout=0.05)
        except Empty:
            continue
        writer.apply_events([event], record_loader=make_record)
        if predicate():
            return monotonic() - started
    raise AssertionError(failure_message)


def test_watch_rename_within_root_updates_search_results_within_500ms(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    root.mkdir()
    original = root / "draft-plan.txt"
    renamed = root / "release-plan.txt"
    original.write_text("rename integration coverage\n", encoding="utf-8")
    rebuild_index(db_path, [RootConfig(path=root)], content_enabled=True)

    conn = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root)

        original.rename(renamed)

        elapsed = _wait_for(
            conn,
            service,
            writer,
            lambda: (
                [hit.file.path for hit in search(conn, "release-plan", limit=5).hits] == [renamed]
                and not search(conn, "draft-plan", limit=5).hits
            ),
            deadline_seconds=0.5,
            failure_message="renamed file did not replace the old query result within 500ms",
        )
    finally:
        service.stop()
        conn.close()

    assert elapsed <= 0.5


def test_watch_move_out_of_root_eventually_removes_query_hit(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    outside = tmp_path / "outside"
    db_path = tmp_path / "database" / "index.db"
    root.mkdir()
    outside.mkdir()
    indexed = root / "move-out.txt"
    relocated = outside / "move-out.txt"
    indexed.write_text("move out integration coverage\n", encoding="utf-8")
    rebuild_index(db_path, [RootConfig(path=root)], content_enabled=True)

    conn = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root)

        indexed.rename(relocated)

        elapsed = _wait_for(
            conn,
            service,
            writer,
            lambda: not search(conn, "move out integration coverage", limit=5).hits,
            deadline_seconds=1.0,
            failure_message="moved-out file remained query-visible after 1s",
        )
    finally:
        service.stop()
        conn.close()

    assert elapsed <= 1.0


def test_watch_move_into_root_adds_query_hit_within_500ms(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    outside = tmp_path / "outside"
    db_path = tmp_path / "database" / "index.db"
    root.mkdir()
    outside.mkdir()
    source = outside / "move-in.txt"
    destination = root / "move-in.txt"
    source.write_text("move in integration coverage\n", encoding="utf-8")
    rebuild_index(db_path, [RootConfig(path=root)], content_enabled=True)

    conn = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root)

        source.rename(destination)

        elapsed = _wait_for(
            conn,
            service,
            writer,
            lambda: [hit.file.path for hit in search(conn, "move in integration coverage", limit=5).hits]
            == [destination],
            deadline_seconds=0.5,
            failure_message="moved-in file did not become query-visible within 500ms",
        )
    finally:
        service.stop()
        conn.close()

    assert elapsed <= 0.5


def test_watch_move_between_roots_eventually_rehomes_result(tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "database" / "index.db"
    root_a.mkdir()
    root_b.mkdir()
    source = root_a / "handoff.txt"
    destination = root_b / "handoff.txt"
    source.write_text("cross root handoff coverage\n", encoding="utf-8")
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

        source.rename(destination)

        elapsed = _wait_for(
            conn,
            service,
            writer,
            lambda: (
                [hit.file.path for hit in search(conn, "cross root handoff coverage", limit=5).hits]
                == [destination]
                and not search(conn, "cross root handoff coverage", limit=5, root=root_a).hits
                and [hit.file.path for hit in search(conn, "cross root handoff coverage", limit=5, root=root_b).hits]
                == [destination]
            ),
            deadline_seconds=1.0,
            failure_message="cross-root move did not rehome the query result within 1s",
        )
    finally:
        service.stop()
        conn.close()

    assert elapsed <= 1.0
