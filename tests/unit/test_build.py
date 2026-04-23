from __future__ import annotations

import sqlite3
from pathlib import Path
from time import time

import pytest

import eodinga.index.build as build_module
from eodinga.common import FileRecord
from eodinga.config import RootConfig
from eodinga.index.build import rebuild_index
from eodinga.index.schema import apply_schema
from eodinga.index.writer import IndexWriter


def test_rebuild_index_failure_keeps_existing_target_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "fresh.txt").write_text("fresh content\n", encoding="utf-8")

    db_path = tmp_path / "index.db"
    conn = sqlite3.connect(db_path)
    try:
        apply_schema(conn)
        conn.execute(
            "INSERT INTO roots(id, path, include, exclude, added_at) VALUES (?, ?, ?, ?, ?)",
            (1, str(tmp_path / "existing-root"), "[]", "[]", 1),
        )
        conn.execute(
            """
            INSERT INTO files (
              id, root_id, path, parent_path, name, name_lower, ext, size, mtime, ctime,
              is_dir, is_symlink, content_hash, indexed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                1,
                "/existing/live.txt",
                "/existing",
                "live.txt",
                "live.txt",
                "txt",
                4,
                1,
                1,
                0,
                0,
                None,
                1,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    original_walk_batched = build_module.walk_batched

    def failing_walk_batched(root_path: Path, rules, root_id: int = 0):
        yield from original_walk_batched(root_path, rules, root_id=root_id)
        raise RuntimeError("simulated rebuild failure")

    monkeypatch.setattr(build_module, "walk_batched", failing_walk_batched)

    with pytest.raises(RuntimeError, match="simulated rebuild failure"):
        rebuild_index(db_path, [RootConfig(path=root)])

    reopened = sqlite3.connect(db_path)
    try:
        rows = reopened.execute("SELECT path FROM files ORDER BY path").fetchall()
        assert [str(row[0]) for row in rows] == ["/existing/live.txt"]
    finally:
        reopened.close()

    staged_path = db_path.with_name(".index.db.next")
    assert not staged_path.exists()
    assert not staged_path.with_name(".index.db.next-wal").exists()


def test_rebuild_index_keeps_bulk_upserts_inside_one_outer_transaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    db_path = tmp_path / "index.db"
    now = int(time())
    records = [
        FileRecord(
            root_id=1,
            path=root / "one.txt",
            parent_path=root,
            name="one.txt",
            name_lower="one.txt",
            ext="txt",
            size=1,
            mtime=now,
            ctime=now,
            is_dir=False,
            is_symlink=False,
            indexed_at=now,
        ),
        FileRecord(
            root_id=1,
            path=root / "two.txt",
            parent_path=root,
            name="two.txt",
            name_lower="two.txt",
            ext="txt",
            size=2,
            mtime=now,
            ctime=now,
            is_dir=False,
            is_symlink=False,
            indexed_at=now,
        ),
    ]
    transaction_states: list[tuple[bool, bool]] = []

    class TrackingWriter(IndexWriter):
        def bulk_upsert(self, batch):
            before = self._conn.in_transaction
            inserted = super().bulk_upsert(batch)
            transaction_states.append((before, self._conn.in_transaction))
            return inserted

    def fake_walk_batched(_root_path: Path, _rules, root_id: int = 0):
        assert root_id == 1
        yield [records[0]]
        yield [records[1]]

    monkeypatch.setattr(build_module, "IndexWriter", TrackingWriter)
    monkeypatch.setattr(build_module, "walk_batched", fake_walk_batched)

    result = rebuild_index(db_path, [RootConfig(path=root)], content_enabled=False)

    assert result.files_indexed == 2
    assert transaction_states == [(True, True), (True, True)]
