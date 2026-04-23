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
    *,
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
        hits = [hit.file.path for hit in search(conn, query, limit=5, root=root).hits]
        if expected_path in hits:
            return min(monotonic() - started, deadline_seconds)
    raise AssertionError(f"{expected_path} did not become query-visible within {deadline_seconds:.3f}s")


def _wait_for_query_miss(
    conn,
    service: WatchService,
    writer: IndexWriter,
    query: str,
    missing_path: Path,
    deadline_seconds: float,
    *,
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
        hits = [hit.file.path for hit in search(conn, query, limit=5, root=root).hits]
        if missing_path not in hits:
            return min(monotonic() - started, deadline_seconds)
    raise AssertionError(f"{missing_path} remained query-visible after {deadline_seconds:.3f}s")


def test_live_create_persists_across_reopen(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    root.mkdir()
    rebuild_index(db_path, [RootConfig(path=root)], content_enabled=True)

    conn = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root)

        created = root / "created-after-index.txt"
        created.write_text("persisted live create after reopen\n", encoding="utf-8")
        elapsed = _wait_for_query_hit(
            conn,
            service,
            writer,
            "persisted live create after reopen",
            created,
            deadline_seconds=0.5,
        )
    finally:
        service.stop()
        conn.close()

    reopened = open_index(db_path)
    try:
        reopened_hits = [hit.file.path for hit in search(reopened, "persisted live create after reopen", limit=5).hits]
    finally:
        reopened.close()

    assert elapsed <= 0.5
    assert reopened_hits == [created]


def test_live_delete_persists_across_reopen(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    root.mkdir()
    target = root / "deleted-after-index.txt"
    target.write_text("persisted live delete after reopen\n", encoding="utf-8")
    rebuild_index(db_path, [RootConfig(path=root)], content_enabled=True)

    conn = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root)

        initial_hits = [hit.file.path for hit in search(conn, "persisted live delete after reopen", limit=5).hits]
        target.unlink()
        elapsed = _wait_for_query_miss(
            conn,
            service,
            writer,
            "persisted live delete after reopen",
            target,
            deadline_seconds=0.5,
        )
    finally:
        service.stop()
        conn.close()

    reopened = open_index(db_path)
    try:
        reopened_hits = [hit.file.path for hit in search(reopened, "persisted live delete after reopen", limit=5).hits]
    finally:
        reopened.close()

    assert initial_hits == [target]
    assert elapsed <= 0.5
    assert reopened_hits == []


def test_live_same_root_move_persists_path_and_query_after_reopen(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    root.mkdir()
    source = root / "draft-note.txt"
    source.write_text("persisted live move after reopen\n", encoding="utf-8")
    rebuild_index(db_path, [RootConfig(path=root)], content_enabled=True)

    conn = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root)

        destination = root / "renamed-note.txt"
        source.rename(destination)
        appeared_elapsed = _wait_for_query_hit(
            conn,
            service,
            writer,
            "persisted live move after reopen",
            destination,
            deadline_seconds=0.5,
        )
        removed_elapsed = _wait_for_query_miss(
            conn,
            service,
            writer,
            "persisted live move after reopen",
            source,
            deadline_seconds=0.5,
        )
    finally:
        service.stop()
        conn.close()

    reopened = open_index(db_path)
    try:
        source_hits = [hit.file.path for hit in search(reopened, "path:draft-note", limit=5).hits]
        destination_hits = [hit.file.path for hit in search(reopened, "path:renamed-note", limit=5).hits]
        reopened_query_hits = [hit.file.path for hit in search(reopened, "persisted live move after reopen", limit=5).hits]
    finally:
        reopened.close()

    assert appeared_elapsed <= 0.5
    assert removed_elapsed <= 0.5
    assert source_hits == []
    assert destination_hits == [destination]
    assert reopened_query_hits == [destination]


def test_live_multi_root_create_persists_global_and_root_scope_after_reopen(tmp_path: Path) -> None:
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

        created = root_b / "beta-created-after-index.txt"
        created.write_text("persisted scoped live create after reopen\n", encoding="utf-8")
        elapsed = _wait_for_query_hit(
            conn,
            service,
            writer,
            "persisted scoped live create after reopen",
            created,
            deadline_seconds=0.5,
            root=root_b,
        )
    finally:
        service.stop()
        conn.close()

    reopened = open_index(db_path)
    try:
        all_hits = {
            hit.file.path
            for hit in search(reopened, "persisted scoped live create after reopen", limit=5).hits
        }
        alpha_hits = {
            hit.file.path
            for hit in search(
                reopened,
                "persisted scoped live create after reopen",
                limit=5,
                root=root_a,
            ).hits
        }
        beta_hits = {
            hit.file.path
            for hit in search(
                reopened,
                "persisted scoped live create after reopen",
                limit=5,
                root=root_b,
            ).hits
        }
    finally:
        reopened.close()

    assert elapsed <= 0.5
    assert all_hits == {created}
    assert alpha_hits == set()
    assert beta_hits == {created}
