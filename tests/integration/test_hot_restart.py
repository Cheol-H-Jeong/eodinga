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
from eodinga.index.storage import has_stale_wal, mark_staged_build_state, open_index
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


def test_hot_restart_reopen_multi_root_delete_stays_root_scoped(tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "database" / "index.db"
    root_a.mkdir()
    root_b.mkdir()
    target = root_a / "existing-alpha.txt"
    survivor = root_b / "existing-beta.txt"
    target.write_text("persisted reopen alpha delete\n", encoding="utf-8")
    survivor.write_text("persisted reopen beta survivor\n", encoding="utf-8")
    rebuild_index(
        db_path,
        [RootConfig(path=root_a), RootConfig(path=root_b)],
        content_enabled=True,
    )

    first_conn = open_index(db_path)
    try:
        initial_hits = {hit.file.path for hit in search(first_conn, "persisted reopen", limit=5).hits}
    finally:
        first_conn.close()

    reopened = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(reopened, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root_a)
        service.start(root_b)

        target.unlink()
        elapsed = _wait_for_query_miss(
            reopened,
            service,
            writer,
            "persisted reopen alpha delete",
            target,
            deadline_seconds=0.5,
        )
        alpha_hits = {
            hit.file.path
            for hit in search(reopened, "persisted reopen", limit=5, root=root_a).hits
        }
        beta_hits = {
            hit.file.path
            for hit in search(reopened, "persisted reopen", limit=5, root=root_b).hits
        }
        remaining_hits = {hit.file.path for hit in search(reopened, "persisted reopen", limit=5).hits}
    finally:
        service.stop()
        reopened.close()

    assert initial_hits == {target, survivor}
    assert elapsed <= 0.5
    assert alpha_hits == set()
    assert beta_hits == {survivor}
    assert remaining_hits == {survivor}


def test_hot_restart_open_index_resumes_interrupted_build_and_accepts_live_updates(
    tmp_path: Path,
) -> None:
    root = tmp_path / "workspace"
    target_db = tmp_path / "database" / "index.db"
    staged_db = tmp_path / "database" / ".index.db.next"
    root.mkdir()
    existing = root / "recovered.txt"
    existing.write_text("interrupted staged build recovery\n", encoding="utf-8")

    rebuild_index(target_db, [RootConfig(path=root)], content_enabled=True)
    rebuild_index(staged_db, [RootConfig(path=root)], content_enabled=True)
    target_db.unlink()
    assert staged_db.exists()

    reopened = open_index(target_db)
    service = WatchService()
    try:
        initial_hits = [hit.file.path for hit in search(reopened, "staged build recovery", limit=3).hits]
        writer = IndexWriter(reopened, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root)

        created = root / "after-build-resume.txt"
        created.write_text("live update after staged resume\n", encoding="utf-8")
        elapsed = _wait_for_query_hit(
            reopened,
            service,
            writer,
            "live update after staged resume",
            created,
            deadline_seconds=0.5,
        )
    finally:
        service.stop()
        reopened.close()

    assert initial_hits == [existing]
    assert elapsed <= 0.5
    assert not staged_db.exists()


def test_hot_restart_ignores_incomplete_interrupted_build_stage(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    target_db = tmp_path / "database" / "index.db"
    staged_db = tmp_path / "database" / ".index.db.next"
    root.mkdir()
    existing = root / "stable.txt"
    existing.write_text("stable restart index\n", encoding="utf-8")

    rebuild_index(target_db, [RootConfig(path=root)], content_enabled=True)

    staged_conn = open_index(staged_db)
    try:
        mark_staged_build_state(staged_conn, complete=False)
        staged_conn.execute(
            "INSERT INTO roots(id, path, include, exclude, added_at) VALUES (?, ?, ?, ?, ?)",
            (1, str(root), "[]", "[]", 1),
        )
        staged_conn.commit()
    finally:
        staged_conn.close()

    reopened = open_index(target_db)
    try:
        hits = [hit.file.path for hit in search(reopened, "stable restart index", limit=3).hits]
        assert hits == [existing]
    finally:
        reopened.close()

    assert not staged_db.exists()
