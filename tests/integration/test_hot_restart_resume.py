from __future__ import annotations

import shutil
from pathlib import Path
from queue import Empty
from time import monotonic

from eodinga.config import RootConfig
from eodinga.content.registry import parse
from eodinga.core.watcher import WatchService
from eodinga.index import open_index
from eodinga.index.build import rebuild_index
from eodinga.index.storage import has_stale_wal
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


def _copy_index_with_sidecars(source: Path, target: Path) -> None:
    shutil.copy2(source, target)
    shutil.copy2(source.with_name(f"{source.name}-wal"), target.with_name(f"{target.name}-wal"))
    shutil.copy2(source.with_name(f"{source.name}-shm"), target.with_name(f"{target.name}-shm"))


def test_hot_restart_resumes_interrupted_build_with_multi_root_scope_and_live_updates(
    tmp_path: Path,
) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    target_db = tmp_path / "database" / "index.db"
    staged_db = tmp_path / "database" / ".index.db.next"
    root_a.mkdir()
    root_b.mkdir()
    alpha = root_a / "existing-alpha.txt"
    beta = root_b / "existing-beta.txt"
    alpha.write_text("multi root staged build alpha\n", encoding="utf-8")
    beta.write_text("multi root staged build beta\n", encoding="utf-8")

    roots = [RootConfig(path=root_a), RootConfig(path=root_b)]
    rebuild_index(target_db, roots, content_enabled=True)
    rebuild_index(staged_db, roots, content_enabled=True)
    target_db.unlink()
    assert staged_db.exists()

    reopened = open_index(target_db)
    service = WatchService()
    try:
        alpha_hits = {
            hit.file.path for hit in search(reopened, "multi root staged build", limit=5, root=root_a).hits
        }
        beta_hits = {
            hit.file.path for hit in search(reopened, "multi root staged build", limit=5, root=root_b).hits
        }

        writer = IndexWriter(reopened, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root_a)
        service.start(root_b)

        created = root_b / "after-resume-beta.txt"
        created.write_text("beta update after staged build resume\n", encoding="utf-8")
        _wait_for_query_hit(
            reopened,
            service,
            writer,
            "beta update after staged build resume",
            created,
            deadline_seconds=0.5,
        )

        resumed_beta_hits = {
            hit.file.path
            for hit in search(reopened, "beta update after staged build resume", limit=5, root=root_b).hits
        }
        resumed_alpha_hits = {
            hit.file.path
            for hit in search(reopened, "beta update after staged build resume", limit=5, root=root_a).hits
        }
    finally:
        service.stop()
        reopened.close()

    assert alpha_hits == {alpha}
    assert beta_hits == {beta}
    assert resumed_alpha_hits == set()
    assert resumed_beta_hits == {created}
    assert not staged_db.exists()


def test_hot_restart_resumes_interrupted_recovery_with_multi_root_scope_and_live_updates(
    tmp_path: Path,
) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    target_db = tmp_path / "database" / "index.db"
    source_db = tmp_path / "source.db"
    staged_db = target_db.with_name(".index.db.recover")
    root_a.mkdir()
    root_b.mkdir()
    alpha = root_a / "recovery-alpha.txt"
    beta = root_b / "recovery-beta.txt"
    alpha.write_text("multi root staged recovery alpha\n", encoding="utf-8")
    beta.write_text("multi root staged recovery beta\n", encoding="utf-8")

    empty = open_index(target_db)
    empty.close()

    source_conn = open_index(source_db)
    try:
        source_conn.execute("PRAGMA wal_autocheckpoint=0;")
        source_conn.execute(
            "INSERT INTO roots(id, path, include, exclude, added_at) VALUES (?, ?, ?, ?, ?)",
            (1, str(root_a), "[]", "[]", 1),
        )
        source_conn.execute(
            "INSERT INTO roots(id, path, include, exclude, added_at) VALUES (?, ?, ?, ?, ?)",
            (2, str(root_b), "[]", "[]", 1),
        )
        source_conn.commit()
        writer = IndexWriter(source_conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        assert writer.bulk_upsert(
            [
                make_record(alpha, root_id=1),
                make_record(beta, root_id=2),
            ]
        ) == 2
        _copy_index_with_sidecars(source_db, staged_db)
    finally:
        source_conn.close()

    assert has_stale_wal(staged_db)

    reopened = open_index(target_db)
    service = WatchService()
    try:
        alpha_hits = {
            hit.file.path for hit in search(reopened, "multi root staged recovery", limit=5, root=root_a).hits
        }
        beta_hits = {
            hit.file.path for hit in search(reopened, "multi root staged recovery", limit=5, root=root_b).hits
        }

        writer = IndexWriter(reopened, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root_a)
        service.start(root_b)

        created = root_a / "after-recovery-alpha.txt"
        created.write_text("alpha update after staged recovery resume\n", encoding="utf-8")
        _wait_for_query_hit(
            reopened,
            service,
            writer,
            "alpha update after staged recovery resume",
            created,
            deadline_seconds=0.5,
        )

        resumed_alpha_hits = {
            hit.file.path
            for hit in search(reopened, "alpha update after staged recovery resume", limit=5, root=root_a).hits
        }
        resumed_beta_hits = {
            hit.file.path
            for hit in search(reopened, "alpha update after staged recovery resume", limit=5, root=root_b).hits
        }
    finally:
        service.stop()
        reopened.close()

    assert alpha_hits == {alpha}
    assert beta_hits == {beta}
    assert resumed_alpha_hits == {created}
    assert resumed_beta_hits == set()
    assert not staged_db.exists()
    assert not staged_db.with_name(".index.db.recover-wal").exists()
    assert not staged_db.with_name(".index.db.recover-shm").exists()
