from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import eodinga.index.build as build_module
from eodinga.config import RootConfig
from eodinga.index.build import InterruptedBuildError, rebuild_index
from eodinga.index.schema import apply_schema
from eodinga.index.storage import open_index


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


def test_rebuild_index_interrupt_preserves_staged_database_for_resume(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "fresh.txt").write_text("fresh content\n", encoding="utf-8")

    db_path = tmp_path / "index.db"
    stop_checks = {"count": 0}

    def stop_requested() -> bool:
        stop_checks["count"] += 1
        return stop_checks["count"] >= 2

    with pytest.raises(InterruptedBuildError, match="staged progress preserved"):
        rebuild_index(db_path, [RootConfig(path=root)], stop_requested=stop_requested)

    staged_path = db_path.with_name(".index.db.next")
    assert not db_path.exists()
    assert staged_path.exists()

    staged_conn = sqlite3.connect(staged_path)
    try:
        rows = staged_conn.execute("SELECT path FROM files ORDER BY path").fetchall()
        assert [str(row[0]) for row in rows] == [str(root), str(root / "fresh.txt")]
    finally:
        staged_conn.close()

    reopened = open_index(db_path)
    try:
        rows = reopened.execute("SELECT path FROM files ORDER BY path").fetchall()
        assert [str(row[0]) for row in rows] == [str(root), str(root / "fresh.txt")]
    finally:
        reopened.close()

    assert not staged_path.exists()
    assert not staged_path.with_name(".index.db.next-wal").exists()
