from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

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
    assert not staged.exists()
    assert not staged.with_name("index.staged.db-wal").exists()
    assert not staged.with_name("index.staged.db-shm").exists()


def test_atomic_replace_index_checkpoints_staged_wal_before_swap(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    target = tmp_path / "index.db"
    staged = tmp_path / "index.staged.db"

    source_conn = sqlite3.connect(source)
    apply_schema(source_conn)
    source_conn.execute("PRAGMA wal_autocheckpoint=0;")
    source_conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        ("/checkpointed", "[]", "[]", 1),
    )
    source_conn.commit()

    shutil.copy2(source, staged)
    shutil.copy2(source.with_name("source.db-wal"), staged.with_name("index.staged.db-wal"))
    shutil.copy2(source.with_name("source.db-shm"), staged.with_name("index.staged.db-shm"))
    source_conn.close()

    assert staged.with_name("index.staged.db-wal").exists()

    atomic_replace_index(staged, target)

    assert _read_root_paths(target) == ["/checkpointed"]
    assert not target.with_name("index.db-wal").exists()
    assert not target.with_name("index.db-shm").exists()


def test_atomic_replace_index_fsyncs_staged_file_and_target_directory(
    tmp_path: Path, monkeypatch
) -> None:
    target = tmp_path / "index.db"
    staged = tmp_path / "index.staged.db"

    staged_conn = sqlite3.connect(staged)
    apply_schema(staged_conn)
    staged_conn.close()

    calls: list[tuple[str, Path]] = []

    def record_file(path: Path) -> None:
        calls.append(("file", path))

    def record_directory(path: Path) -> None:
        calls.append(("dir", path))

    monkeypatch.setattr("eodinga.index.storage._fsync_file", record_file)
    monkeypatch.setattr("eodinga.index.storage._fsync_directory", record_directory)

    atomic_replace_index(staged, target)

    assert calls == [
        ("file", staged),
        ("dir", target.parent),
        ("file", target),
        ("dir", target.parent),
    ]


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


def test_recover_stale_wal_returns_false_without_sidecars(tmp_path: Path) -> None:
    path = tmp_path / "index.db"
    conn = sqlite3.connect(path)
    apply_schema(conn)
    conn.close()

    assert recover_stale_wal(path) is False


def test_recover_stale_wal_returns_false_when_nonempty_sidecar_survives(
    tmp_path: Path, monkeypatch
) -> None:
    path = tmp_path / "index.db"
    conn = sqlite3.connect(path)
    apply_schema(conn)
    conn.close()
    wal_path = path.with_name("index.db-wal")
    wal_path.write_bytes(b"stale")

    def leave_nonempty_sidecar(_path: Path) -> None:
        wal_path.write_bytes(b"stale")

    monkeypatch.setattr("eodinga.index.storage._checkpoint_wal", leave_nonempty_sidecar)

    assert recover_stale_wal(path) is False
    assert wal_path.read_bytes() == b"stale"


def test_open_index_raises_when_stale_wal_recovery_fails(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "index.db"
    conn = sqlite3.connect(path)
    apply_schema(conn)
    conn.close()

    monkeypatch.setattr("eodinga.index.storage.has_stale_wal", lambda _path: True)
    monkeypatch.setattr("eodinga.index.storage.recover_stale_wal", lambda _path: False)

    with pytest.raises(RuntimeError, match="failed to recover stale WAL"):
        open_index(path)
