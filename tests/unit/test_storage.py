from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from eodinga.index.schema import apply_schema
from eodinga.index.storage import atomic_replace_index, has_stale_wal, open_index, recover_stale_wal


def _read_root_paths(db_path: Path) -> list[str]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT path FROM roots ORDER BY path").fetchall()
        return [str(row[0]) for row in rows]
    finally:
        conn.close()


def test_atomic_replace_index_swaps_in_staged_database(tmp_path: Path) -> None:
    target = tmp_path / "index.db"
    staged = tmp_path / "index.staged.db"

    old_conn = sqlite3.connect(target)
    apply_schema(old_conn)
    old_conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        ("/old", "[]", "[]", 1),
    )
    old_conn.commit()
    old_conn.close()
    target.with_name("index.db-wal").write_bytes(b"stale")
    target.with_name("index.db-shm").write_bytes(b"stale")

    staged_conn = sqlite3.connect(staged)
    apply_schema(staged_conn)
    staged_conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        ("/new", "[]", "[]", 1),
    )
    staged_conn.commit()
    staged_conn.close()

    atomic_replace_index(staged, target)

    assert _read_root_paths(target) == ["/new"]
    assert not target.with_name("index.db-wal").exists()
    assert not target.with_name("index.db-shm").exists()


def test_open_index_replays_stale_wal_on_startup(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    snapshot = tmp_path / "snapshot.db"

    conn = sqlite3.connect(source)
    apply_schema(conn)
    conn.execute("PRAGMA wal_autocheckpoint=0;")
    conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        ("/recovered", "[]", "[]", 1),
    )
    conn.commit()

    shutil.copy2(source, snapshot)
    shutil.copy2(source.with_name("source.db-wal"), snapshot.with_name("snapshot.db-wal"))
    shutil.copy2(source.with_name("source.db-shm"), snapshot.with_name("snapshot.db-shm"))
    conn.close()

    assert has_stale_wal(snapshot)

    recovered = recover_stale_wal(snapshot)
    assert recovered is True

    reopened = open_index(snapshot)
    try:
        rows = reopened.execute("SELECT path FROM roots").fetchall()
        assert [str(row[0]) for row in rows] == ["/recovered"]
    finally:
        reopened.close()
    wal_path = snapshot.with_name("snapshot.db-wal")
    assert not wal_path.exists() or wal_path.stat().st_size == 0
