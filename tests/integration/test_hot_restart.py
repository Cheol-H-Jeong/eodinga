from __future__ import annotations

import shutil
from pathlib import Path

from eodinga.common import PathRules
from eodinga.content.registry import parse
from eodinga.index.storage import has_stale_wal, open_index
from eodinga.index.writer import IndexWriter
from eodinga.core.walker import walk_batched
from eodinga.query import search


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
