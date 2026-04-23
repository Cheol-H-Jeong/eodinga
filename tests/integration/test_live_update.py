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


def _wait_for_query_state(
    conn,
    service: WatchService,
    writer: IndexWriter,
    query: str,
    deadline_seconds: float,
    *,
    expected_paths: set[Path],
    root: Path | None = None,
) -> float:
    started = monotonic()
    deadline = started + deadline_seconds
    while monotonic() < deadline:
        try:
            event = service.queue.get(timeout=0.05)
        except Empty:
            continue
        writer.apply_events([event], record_loader=make_record)
        hits = {
            hit.file.path for hit in search(conn, query, limit=10, root=root).hits
        }
        if hits == expected_paths:
            return monotonic() - started
    raise AssertionError(
        f"query {query!r} did not reach expected paths {sorted(str(path) for path in expected_paths)} "
        f"within {deadline_seconds:.3f}s"
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


def test_live_move_renames_query_visibility_within_500ms(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    root.mkdir()
    source = root / "draft-note.txt"
    destination = root / "final-note.txt"
    source.write_text("rename me for launch handoff\n", encoding="utf-8")
    rebuild_index(db_path, [RootConfig(path=root)], content_enabled=True)

    conn = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root)

        initial_hits = [hit.file.path for hit in search(conn, "rename me handoff", limit=5).hits]
        source.rename(destination)

        elapsed = _wait_for_query_state(
            conn,
            service,
            writer,
            "rename me handoff",
            deadline_seconds=0.5,
            expected_paths={destination},
        )
    finally:
        service.stop()
        conn.close()

    assert initial_hits == [source]
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


def test_live_cross_root_move_updates_root_scoped_results(tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "database" / "index.db"
    root_a.mkdir()
    root_b.mkdir()
    moved = root_a / "shared-note.txt"
    destination = root_b / "shared-note.txt"
    moved.write_text("cross root handoff visibility\n", encoding="utf-8")
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

        initial_alpha_hits = [
            hit.file.path
            for hit in search(conn, "cross root handoff visibility", limit=5, root=root_a).hits
        ]
        initial_beta_hits = [
            hit.file.path
            for hit in search(conn, "cross root handoff visibility", limit=5, root=root_b).hits
        ]

        moved.rename(destination)

        elapsed = _wait_for_query_state(
            conn,
            service,
            writer,
            "cross root handoff visibility",
            deadline_seconds=1.5,
            expected_paths={destination},
        )
        alpha_hits = [
            hit.file.path
            for hit in search(conn, "cross root handoff visibility", limit=5, root=root_a).hits
        ]
        beta_hits = [
            hit.file.path
            for hit in search(conn, "cross root handoff visibility", limit=5, root=root_b).hits
        ]
    finally:
        service.stop()
        conn.close()

    assert initial_alpha_hits == [moved]
    assert initial_beta_hits == []
    assert elapsed <= 1.5
    assert alpha_hits == []
    assert beta_hits == [destination]


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


def test_hot_restart_reopen_accepts_live_delete_within_500ms(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    root.mkdir()
    existing = root / "existing.txt"
    existing.write_text("persisted restart delete visibility\n", encoding="utf-8")
    rebuild_index(db_path, [RootConfig(path=root)], content_enabled=True)

    first_conn = open_index(db_path)
    try:
        initial_hits = [hit.file.path for hit in search(first_conn, "restart delete visibility", limit=3).hits]
    finally:
        first_conn.close()

    reopened = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(reopened, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root)

        existing.unlink()
        elapsed = _wait_for_query_miss(
            reopened,
            service,
            writer,
            "restart delete visibility",
            existing,
            deadline_seconds=0.5,
        )
    finally:
        service.stop()
        reopened.close()

    assert initial_hits == [existing]
    assert elapsed <= 0.5
