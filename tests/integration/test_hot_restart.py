from __future__ import annotations

import shutil
from pathlib import Path
from queue import Empty
from time import monotonic

from eodinga.config import RootConfig
from eodinga.common import PathRules
from eodinga.content.registry import parse
from eodinga.core.watcher import WatchService
from eodinga.index.build import rebuild_index
from eodinga.index.storage import has_stale_wal, open_index
from eodinga.index.writer import IndexWriter
from eodinga.core.walker import walk_batched
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


def test_hot_restart_recovers_stale_wal_and_preserves_queries(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    target = root / "restart-notes.txt"
    target.write_text("restart recovery checklist\n", encoding="utf-8")

    source = tmp_path / "source.db"
    snapshot = tmp_path / "snapshot.db"

    conn = open_index(source)
    try:
        conn.execute("PRAGMA wal_autocheckpoint=0;")
        conn.execute(
            "INSERT INTO roots(id, path, include, exclude, added_at) VALUES (?, ?, ?, ?, ?)",
            (1, str(root), "[]", "[]", 1),
        )
        conn.commit()
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        rules = PathRules(root=root, include=(str(root), f"{root}/**"), exclude=())
        records = [
            record
            for batch in walk_batched(root, rules, root_id=1)
            for record in batch
        ]
        assert writer.bulk_upsert(records) == len(records)

        shutil.copy2(source, snapshot)
        shutil.copy2(source.with_name("source.db-wal"), snapshot.with_name("snapshot.db-wal"))
        shutil.copy2(source.with_name("source.db-shm"), snapshot.with_name("snapshot.db-shm"))
    finally:
        conn.close()

    assert has_stale_wal(snapshot)

    reopened = open_index(snapshot)
    try:
        hits = [hit.file.name for hit in search(reopened, "restart recovery", limit=3).hits]
        assert hits == ["restart-notes.txt"]
    finally:
        reopened.close()

    for suffix in ("-wal", "-shm"):
        sidecar = snapshot.with_name(f"{snapshot.name}{suffix}")
        assert not sidecar.exists()


def test_hot_restart_resumes_interrupted_recovery_stage(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    target = root / "resume-notes.txt"
    target.write_text("resume staged recovery search\n", encoding="utf-8")

    source = tmp_path / "source.db"
    target_db = tmp_path / "index.db"
    staged_db = tmp_path / ".index.db.recover"

    target_conn = open_index(target_db)
    try:
        target_conn.execute(
            "INSERT INTO roots(id, path, include, exclude, added_at) VALUES (?, ?, ?, ?, ?)",
            (1, str(root), "[]", "[]", 1),
        )
        target_conn.commit()
    finally:
        target_conn.close()

    source_conn = open_index(source)
    try:
        source_conn.execute("PRAGMA wal_autocheckpoint=0;")
        source_conn.execute(
            "INSERT INTO roots(id, path, include, exclude, added_at) VALUES (?, ?, ?, ?, ?)",
            (1, str(root), "[]", "[]", 1),
        )
        source_conn.commit()
        writer = IndexWriter(source_conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        rules = PathRules(root=root, include=(str(root), f"{root}/**"), exclude=())
        records = [
            record
            for batch in walk_batched(root, rules, root_id=1)
            for record in batch
        ]
        assert writer.bulk_upsert(records) == len(records)

        shutil.copy2(source, staged_db)
        shutil.copy2(source.with_name("source.db-wal"), staged_db.with_name(".index.db.recover-wal"))
        shutil.copy2(source.with_name("source.db-shm"), staged_db.with_name(".index.db.recover-shm"))
    finally:
        source_conn.close()

    reopened = open_index(target_db)
    try:
        hits = [hit.file.name for hit in search(reopened, "resume staged recovery", limit=3).hits]
        assert hits == ["resume-notes.txt"]
    finally:
        reopened.close()

    assert not staged_db.exists()
    for suffix in ("-wal", "-shm"):
        sidecar = staged_db.with_name(f"{staged_db.name}{suffix}")
        assert not sidecar.exists()


def test_hot_restart_reopen_multi_root_keeps_queries_and_accepts_live_updates(tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "database" / "index.db"
    root_a.mkdir()
    root_b.mkdir()
    existing_a = root_a / "existing-alpha.txt"
    existing_b = root_b / "existing-beta.txt"
    existing_a.write_text("persisted multi root alpha\n", encoding="utf-8")
    existing_b.write_text("persisted multi root beta\n", encoding="utf-8")
    rebuild_index(
        db_path,
        [RootConfig(path=root_a), RootConfig(path=root_b)],
        content_enabled=True,
    )

    first_conn = open_index(db_path)
    try:
        initial_hits = {hit.file.path for hit in search(first_conn, "persisted multi root", limit=5).hits}
        initial_beta_hits = {
            hit.file.path
            for hit in search(first_conn, "persisted multi root", limit=5, root=root_b).hits
        }
    finally:
        first_conn.close()

    reopened = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(reopened, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root_a)
        service.start(root_b)

        created = root_b / "after-reopen-beta.txt"
        created.write_text("post reopen beta update\n", encoding="utf-8")
        elapsed = _wait_for_query_hit(
            reopened,
            service,
            writer,
            "post reopen beta update",
            created,
            deadline_seconds=0.5,
        )
        reopened_hits = {hit.file.path for hit in search(reopened, "persisted multi root", limit=5).hits}
        reopened_beta_hits = {
            hit.file.path
            for hit in search(reopened, "persisted multi root", limit=5, root=root_b).hits
        }
    finally:
        service.stop()
        reopened.close()

    assert initial_hits == {existing_a, existing_b}
    assert initial_beta_hits == {existing_b}
    assert elapsed <= 0.5
    assert reopened_hits == {existing_a, existing_b}
    assert reopened_beta_hits == {existing_b}


def test_hot_restart_persists_live_create_and_delete_across_reopen(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    root.mkdir()
    removed = root / "remove-after-watch.txt"
    removed.write_text("restart deleted query\n", encoding="utf-8")
    rebuild_index(db_path, [RootConfig(path=root)], content_enabled=True)

    conn = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root)

        created = root / "persist-after-watch.txt"
        created.write_text("restart created query\n", encoding="utf-8")
        created_elapsed = _wait_for_query_hit(
            conn,
            service,
            writer,
            "restart created query",
            created,
            deadline_seconds=0.5,
        )

        initial_removed_hits = [
            hit.file.path for hit in search(conn, "restart deleted query", limit=5).hits
        ]
        removed.unlink()
        deleted_elapsed = _wait_for_query_miss(
            conn,
            service,
            writer,
            "restart deleted query",
            removed,
            deadline_seconds=0.5,
        )
    finally:
        service.stop()
        conn.close()

    reopened = open_index(db_path)
    try:
        created_hits = [hit.file.path for hit in search(reopened, "restart created query", limit=5).hits]
        deleted_hits = [hit.file.path for hit in search(reopened, "restart deleted query", limit=5).hits]
    finally:
        reopened.close()

    assert created_elapsed <= 0.5
    assert initial_removed_hits == [removed]
    assert deleted_elapsed <= 0.5
    assert created_hits == [created]
    assert deleted_hits == []
