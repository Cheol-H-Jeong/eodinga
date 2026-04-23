from __future__ import annotations

import signal
import sqlite3
from pathlib import Path

import pytest

import eodinga.index.build as build_module
from eodinga.content.base import ParsedContent
from eodinga.config import RootConfig
from eodinga.index.build import rebuild_index
from eodinga.index.schema import apply_schema


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


def test_rebuild_index_defers_sigterm_until_current_batch_commits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    indexed_file = root / "fresh.txt"
    indexed_file.write_text("fresh content\n", encoding="utf-8")

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

    registered_handlers: dict[int, object] = {}

    monkeypatch.setattr(build_module.signal, "getsignal", lambda _signum: signal.SIG_DFL)

    def capture_signal(signum: int, handler: object) -> object:
        registered_handlers[signum] = handler
        return handler

    monkeypatch.setattr(build_module.signal, "signal", capture_signal)

    interrupted = False

    def parse_and_interrupt(path: Path, *, max_body_chars: int = 4096) -> ParsedContent:
        nonlocal interrupted
        if not interrupted:
            interrupted = True
            handler = registered_handlers[int(signal.SIGTERM)]
            assert callable(handler)
            handler(signal.SIGTERM, None)
        return ParsedContent(
            title=path.name,
            head_text=path.name[:max_body_chars],
            body_text=path.read_text(encoding="utf-8")[:max_body_chars],
            content_sha=b"fresh-sha",
        )

    monkeypatch.setattr(build_module, "parse", parse_and_interrupt)

    original_cleanup = build_module._cleanup_index_files
    staged_rows: list[str] = []
    staged_roots: list[str] = []

    def capture_cleanup(path: Path) -> None:
        if path.exists():
            staged_conn = sqlite3.connect(path)
            try:
                staged_rows.extend(
                    str(row[0])
                    for row in staged_conn.execute("SELECT path FROM files ORDER BY path").fetchall()
                )
                staged_roots.extend(
                    str(row[0])
                    for row in staged_conn.execute("SELECT path FROM roots ORDER BY id").fetchall()
                )
            finally:
                staged_conn.close()
        original_cleanup(path)

    monkeypatch.setattr(build_module, "_cleanup_index_files", capture_cleanup)

    with pytest.raises(build_module.RebuildInterrupted, match="SIGTERM"):
        rebuild_index(db_path, [RootConfig(path=root)])

    reopened = sqlite3.connect(db_path)
    try:
        rows = reopened.execute("SELECT path FROM files ORDER BY path").fetchall()
        assert [str(row[0]) for row in rows] == ["/existing/live.txt"]
    finally:
        reopened.close()

    assert staged_rows == [str(root), str(indexed_file)]
    assert staged_roots == [str(root)]

    staged_path = db_path.with_name(".index.db.next")
    assert not staged_path.exists()
    assert not staged_path.with_name(".index.db.next-wal").exists()
