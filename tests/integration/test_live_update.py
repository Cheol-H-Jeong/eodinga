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
        hits = [hit.file.path for hit in search(conn, query, limit=5).hits]
        if expected_path in hits:
            return monotonic() - started
    raise AssertionError(f"{expected_path} did not become query-visible within {deadline_seconds:.3f}s")


def _wait_for_query_miss(
    conn,
    service: WatchService,
    writer: IndexWriter,
    query: str,
    missing_path: Path,
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
        hits = [hit.file.path for hit in search(conn, query, limit=5).hits]
        if missing_path not in hits:
            return monotonic() - started
    raise AssertionError(f"{missing_path} remained query-visible after {deadline_seconds:.3f}s")


def _wait_for_search_paths(
    conn,
    service: WatchService,
    writer: IndexWriter,
    query: str,
    *,
    deadline_seconds: float,
    root: Path | None = None,
    expected_paths: set[Path],
) -> tuple[float, set[Path]]:
    started = monotonic()
    deadline = started + deadline_seconds
    latest_paths = {
        hit.file.path for hit in search(conn, query, limit=10, root=root).hits
    }
    if latest_paths == expected_paths:
        return 0.0, latest_paths
    while monotonic() < deadline:
        try:
            event = service.queue.get(timeout=0.05)
        except Empty:
            continue
        writer.apply_events([event], record_loader=make_record)
        latest_paths = {
            hit.file.path for hit in search(conn, query, limit=10, root=root).hits
        }
        if latest_paths == expected_paths:
            return monotonic() - started, latest_paths
    raise AssertionError(
        f"query {query!r} did not settle to {expected_paths!r} within {deadline_seconds:.3f}s; "
        f"last seen {latest_paths!r}"
    )


def test_live_update_visible_to_search_within_500ms(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    root.mkdir()
    rebuild_index(db_path, [RootConfig(path=root)], content_enabled=True)

    conn = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root)

        created = root / "live-update.txt"
        created.write_text("live update integration coverage\n", encoding="utf-8")

        elapsed = _wait_for_query_hit(
            conn,
            service,
            writer,
            "integration coverage",
            created,
            deadline_seconds=0.5,
        )
    finally:
        service.stop()
        conn.close()

    assert elapsed <= 0.5


def test_live_delete_removed_from_search_within_500ms(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    root.mkdir()
    target = root / "live-delete.txt"
    target.write_text("live delete integration coverage\n", encoding="utf-8")
    rebuild_index(db_path, [RootConfig(path=root)], content_enabled=True)

    conn = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root)

        initial_hits = [hit.file.path for hit in search(conn, "delete integration coverage", limit=5).hits]
        target.unlink()

        elapsed = _wait_for_query_miss(
            conn,
            service,
            writer,
            "delete integration coverage",
            target,
            deadline_seconds=0.5,
        )
    finally:
        service.stop()
        conn.close()

    assert initial_hits == [target]
    assert elapsed <= 0.5


def test_live_update_visible_with_multi_root_watchers_and_root_scope(tmp_path: Path) -> None:
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

        created = root_b / "beta-live-update.txt"
        created.write_text("beta scoped integration visibility\n", encoding="utf-8")

        elapsed = _wait_for_query_hit(
            conn,
            service,
            writer,
            "scoped integration visibility",
            created,
            deadline_seconds=0.5,
        )
        alpha_hits = [
            hit.file.path
            for hit in search(conn, "scoped integration visibility", limit=5, root=root_a).hits
        ]
        beta_hits = [
            hit.file.path
            for hit in search(conn, "scoped integration visibility", limit=5, root=root_b).hits
        ]
    finally:
        service.stop()
        conn.close()

    assert elapsed <= 0.5
    assert alpha_hits == []
    assert beta_hits == [created]


def test_live_delete_removed_with_multi_root_watchers_and_root_scope(tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "database" / "index.db"
    root_a.mkdir()
    root_b.mkdir()
    survivor = root_a / "alpha-keep.txt"
    target = root_b / "beta-live-delete.txt"
    survivor.write_text("alpha scoped integration retention\n", encoding="utf-8")
    target.write_text("beta scoped integration deletion\n", encoding="utf-8")
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

        initial_hits = [hit.file.path for hit in search(conn, "scoped integration deletion", limit=5).hits]
        initial_beta_hits = [
            hit.file.path
            for hit in search(conn, "scoped integration deletion", limit=5, root=root_b).hits
        ]
        target.unlink()

        elapsed = _wait_for_query_miss(
            conn,
            service,
            writer,
            "scoped integration deletion",
            target,
            deadline_seconds=0.5,
        )
        alpha_hits = [
            hit.file.path
            for hit in search(conn, "scoped integration retention", limit=5, root=root_a).hits
        ]
        beta_hits = [
            hit.file.path
            for hit in search(conn, "scoped integration deletion", limit=5, root=root_b).hits
        ]
    finally:
        service.stop()
        conn.close()

    assert initial_hits == [target]
    assert initial_beta_hits == [target]
    assert elapsed <= 0.5
    assert alpha_hits == [survivor]
    assert beta_hits == []


def test_live_move_between_watched_roots_rehomes_query_hit_and_root_scope(tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "database" / "index.db"
    root_a.mkdir()
    root_b.mkdir()
    source = root_a / "cross-root.txt"
    destination = root_b / "cross-root.txt"
    source.write_text("cross root live move coverage\n", encoding="utf-8")
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

        initial_hits = {
            hit.file.path for hit in search(conn, "cross root live move coverage", limit=10).hits
        }
        source.rename(destination)

        elapsed, hits = _wait_for_search_paths(
            conn,
            service,
            writer,
            "cross root live move coverage",
            deadline_seconds=1.0,
            expected_paths={destination},
        )
        _, alpha_hits = _wait_for_search_paths(
            conn,
            service,
            writer,
            "cross root live move coverage",
            deadline_seconds=0.1,
            root=root_a,
            expected_paths=set(),
        )
        _, beta_hits = _wait_for_search_paths(
            conn,
            service,
            writer,
            "cross root live move coverage",
            deadline_seconds=0.1,
            root=root_b,
            expected_paths={destination},
        )
    finally:
        service.stop()
        conn.close()

    assert initial_hits == {source}
    assert elapsed <= 1.0
    assert hits == {destination}
    assert alpha_hits == set()
    assert beta_hits == {destination}


def test_hot_restart_reopen_keeps_queries_and_accepts_live_updates(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    root.mkdir()
    existing = root / "existing.txt"
    existing.write_text("persisted restart query\n", encoding="utf-8")
    rebuild_index(db_path, [RootConfig(path=root)], content_enabled=True)

    first_conn = open_index(db_path)
    try:
        initial_hits = [hit.file.path for hit in search(first_conn, "persisted restart", limit=3).hits]
    finally:
        first_conn.close()

    reopened = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(reopened, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root)

        created = root / "after-reopen.txt"
        created.write_text("post reopen live update\n", encoding="utf-8")
        _wait_for_query_hit(
            reopened,
            service,
            writer,
            "post reopen",
            created,
            deadline_seconds=0.5,
        )
        reopened_hits = [hit.file.path for hit in search(reopened, "persisted restart", limit=3).hits]
    finally:
        service.stop()
        reopened.close()

    assert initial_hits == [existing]
    assert reopened_hits == [existing]
