from __future__ import annotations

import shutil
import sqlite3
from typing import Any
from pathlib import Path

import pytest

import eodinga.index.storage as storage_module
from eodinga.index.schema import apply_schema
from eodinga.index.storage import (
    SQLITE_CACHED_STATEMENTS,
    atomic_replace_index,
    connect_database,
    discard_incomplete_interrupted_build,
    has_stale_wal,
    has_resumable_interrupted_build,
    mark_build_stage_complete,
    open_index,
    recover_interrupted_build,
    recover_interrupted_recovery,
    recover_stale_wal,
    temporary_pragmas,
)


def _read_root_paths(db_path: Path) -> list[str]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT path FROM roots ORDER BY path").fetchall()
        return [str(row[0]) for row in rows]
    finally:
        conn.close()


def _make_recovery_snapshot(source: Path, snapshot: Path) -> None:
    shutil.copy2(source, snapshot)
    shutil.copy2(source.with_name(f"{source.name}-wal"), snapshot.with_name(f"{snapshot.name}-wal"))
    shutil.copy2(source.with_name(f"{source.name}-shm"), snapshot.with_name(f"{snapshot.name}-shm"))


def _mark_staged_build_ready(staged_path: Path) -> None:
    mark_build_stage_complete(staged_path)


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


def test_cleanup_index_files_fsyncs_parent_directory_when_durable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "index.db"
    path.write_bytes(b"sqlite")
    path.with_name("index.db-wal").write_bytes(b"wal")
    path.with_name("index.db-shm").write_bytes(b"shm")
    calls: list[Path] = []

    monkeypatch.setattr("eodinga.index.storage._fsync_directory", lambda target: calls.append(target))

    assert storage_module._cleanup_index_files(path, durable=True) is True
    assert calls == [tmp_path]
    assert not path.exists()
    assert not path.with_name("index.db-wal").exists()
    assert not path.with_name("index.db-shm").exists()


def test_copy_index_with_sidecars_fsyncs_promoted_sidecars(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source.db"
    target = tmp_path / ".index.db.recover"

    conn = sqlite3.connect(source)
    try:
        apply_schema(conn)
        conn.execute("PRAGMA wal_autocheckpoint=0;")
        conn.execute(
            "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
            ("/checkpointed", "[]", "[]", 1),
        )
        conn.commit()
        assert source.with_name("source.db-wal").exists()
        assert source.with_name("source.db-shm").exists()

        calls: list[tuple[str, Path]] = []

        def record_file(path: Path) -> None:
            calls.append(("file", path))

        def record_directory(path: Path) -> None:
            calls.append(("dir", path))

        monkeypatch.setattr("eodinga.index.storage._fsync_file", record_file)
        monkeypatch.setattr("eodinga.index.storage._fsync_directory", record_directory)

        storage_module._copy_index_with_sidecars(source, target)

        assert ("file", target) in calls
        assert ("file", target.with_name(".index.db.recover-wal")) in calls
        assert ("file", target.with_name(".index.db.recover-shm")) in calls
        assert calls.count(("dir", target.parent)) == 2
    finally:
        conn.close()


def test_atomic_replace_index_preserves_live_sidecars_when_swap_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "index.db"
    staged = tmp_path / "index.staged.db"

    target_conn = sqlite3.connect(target)
    apply_schema(target_conn)
    target_conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        ("/live", "[]", "[]", 1),
    )
    target_conn.commit()
    target_conn.close()
    target_wal = target.with_name("index.db-wal")
    target_shm = target.with_name("index.db-shm")
    target_wal.write_bytes(b"live-wal")
    target_shm.write_bytes(b"live-shm")

    staged_conn = sqlite3.connect(staged)
    apply_schema(staged_conn)
    staged_conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        ("/staged", "[]", "[]", 1),
    )
    staged_conn.commit()
    staged_conn.close()

    def fail_replace(_source: Path, _target: Path) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr("eodinga.index.storage.os.replace", fail_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        atomic_replace_index(staged, target)

    assert target_wal.read_bytes() == b"live-wal"
    assert target_shm.read_bytes() == b"live-shm"
    assert staged.exists()
    assert _read_root_paths(target) == ["/live"]


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

    _make_recovery_snapshot(source, snapshot)
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


def test_connect_database_applies_row_factory_and_pragmas(tmp_path: Path) -> None:
    path = tmp_path / "index.db"

    conn = connect_database(path)
    try:
        assert conn.row_factory is sqlite3.Row
        cache_size = conn.execute("PRAGMA cache_size;").fetchone()
        assert cache_size is not None
        assert int(cache_size[0]) == -64000
    finally:
        conn.close()


def test_connect_database_accepts_disabled_row_factory(tmp_path: Path) -> None:
    path = tmp_path / "index.db"

    conn = connect_database(path, row_factory=None)
    try:
        assert conn.row_factory is None
    finally:
        conn.close()


def test_connect_database_uses_explicit_statement_cache_budget(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "index.db"
    seen: dict[str, object] = {}
    original_connect = sqlite3.connect

    def fake_connect(database: str | bytes | Path, *args: Any, **kwargs: Any) -> sqlite3.Connection:
        seen["database"] = database
        seen["cached_statements"] = kwargs.get("cached_statements")
        return original_connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", fake_connect)

    conn = connect_database(path)
    try:
        assert seen["database"] == path
        assert seen["cached_statements"] == SQLITE_CACHED_STATEMENTS
    finally:
        conn.close()


def test_temporary_pragmas_override_then_restore_values(tmp_path: Path) -> None:
    path = tmp_path / "index.db"
    conn = connect_database(path)
    try:
        baseline = conn.execute("PRAGMA synchronous;").fetchone()
        assert baseline is not None
        baseline_value = int(baseline[0])

        with temporary_pragmas(conn, {"synchronous": "FULL", "cache_size": -1024}):
            synchronous = conn.execute("PRAGMA synchronous;").fetchone()
            cache_size = conn.execute("PRAGMA cache_size;").fetchone()
            assert synchronous is not None
            assert cache_size is not None
            assert int(synchronous[0]) == 2
            assert int(cache_size[0]) == -1024

        restored = conn.execute("PRAGMA synchronous;").fetchone()
        restored_cache = conn.execute("PRAGMA cache_size;").fetchone()
        assert restored is not None
        assert restored_cache is not None
        assert int(restored[0]) == baseline_value
        assert int(restored_cache[0]) == -64000
    finally:
        conn.close()


def test_temporary_pragmas_restores_values_after_error(tmp_path: Path) -> None:
    path = tmp_path / "index.db"
    conn = connect_database(path)
    try:
        with pytest.raises(RuntimeError, match="boom"):
            with temporary_pragmas(conn, {"cache_size": -2048}):
                raise RuntimeError("boom")

        cache_size = conn.execute("PRAGMA cache_size;").fetchone()
        assert cache_size is not None
        assert int(cache_size[0]) == -64000
    finally:
        conn.close()


def test_temporary_pragmas_is_noop_inside_active_transaction(tmp_path: Path) -> None:
    path = tmp_path / "index.db"
    conn = connect_database(path)
    try:
        baseline = conn.execute("PRAGMA synchronous;").fetchone()
        assert baseline is not None
        conn.execute("BEGIN")
        with temporary_pragmas(conn, {"synchronous": "NORMAL", "cache_size": -2048}):
            synchronous = conn.execute("PRAGMA synchronous;").fetchone()
            cache_size = conn.execute("PRAGMA cache_size;").fetchone()
            assert synchronous is not None
            assert cache_size is not None
            assert int(synchronous[0]) == int(baseline[0])
            assert int(cache_size[0]) == -64000
        conn.rollback()
    finally:
        conn.close()


def test_temporary_pragmas_skips_redundant_overrides(tmp_path: Path) -> None:
    path = tmp_path / "index.db"
    conn = connect_database(path)
    statements: list[str] = []
    try:
        conn.set_trace_callback(statements.append)
        with temporary_pragmas(conn, {"synchronous": "FULL", "cache_size": -64000}):
            pass
    finally:
        conn.set_trace_callback(None)
        conn.close()

    pragma_sets = [statement for statement in statements if statement.startswith("PRAGMA ")]
    assert pragma_sets == ["PRAGMA synchronous;", "PRAGMA cache_size;"]


def test_temporary_pragmas_skips_redundant_nested_overrides(tmp_path: Path) -> None:
    path = tmp_path / "index.db"
    conn = connect_database(path)
    statements: list[str] = []
    try:
        conn.set_trace_callback(statements.append)
        with temporary_pragmas(conn, {"synchronous": "NORMAL", "cache_size": -128000}):
            with temporary_pragmas(conn, {"synchronous": "NORMAL", "cache_size": -128000}):
                pass
    finally:
        conn.set_trace_callback(None)
        conn.close()

    pragma_sets = [statement for statement in statements if statement.startswith("PRAGMA ")]
    assert pragma_sets == [
        "PRAGMA synchronous;",
        "PRAGMA synchronous=NORMAL;",
        "PRAGMA cache_size;",
        "PRAGMA cache_size=-128000;",
        "PRAGMA cache_size=-64000;",
        "PRAGMA synchronous=2;",
    ]


def test_temporary_pragmas_restores_outer_override_after_nested_override(tmp_path: Path) -> None:
    path = tmp_path / "index.db"
    conn = connect_database(path)
    try:
        with temporary_pragmas(conn, {"synchronous": "NORMAL"}):
            outer = conn.execute("PRAGMA synchronous;").fetchone()
            assert outer is not None
            assert int(outer[0]) == 1
            with temporary_pragmas(conn, {"synchronous": "FULL"}):
                inner = conn.execute("PRAGMA synchronous;").fetchone()
                assert inner is not None
                assert int(inner[0]) == 2
            restored_outer = conn.execute("PRAGMA synchronous;").fetchone()
            assert restored_outer is not None
            assert int(restored_outer[0]) == 1

        final = conn.execute("PRAGMA synchronous;").fetchone()
        assert final is not None
        assert int(final[0]) == 2
    finally:
        conn.close()


def test_recover_stale_wal_returns_false_when_nonempty_sidecar_survives(
    tmp_path: Path, monkeypatch
) -> None:
    path = tmp_path / "index.db"
    conn = sqlite3.connect(path)
    apply_schema(conn)
    conn.close()
    wal_path = path.with_name("index.db-wal")
    wal_path.write_bytes(b"stale")
    staged_path = path.with_name(".index.db.recover")
    staged_wal_path = staged_path.with_name(".index.db.recover-wal")

    def leave_nonempty_sidecar(recovery_path: Path) -> None:
        assert recovery_path == staged_path
        staged_wal_path.write_bytes(b"stale")

    monkeypatch.setattr("eodinga.index.storage._checkpoint_wal", leave_nonempty_sidecar)

    assert recover_stale_wal(path) is False
    assert wal_path.read_bytes() == b"stale"
    assert not staged_path.exists()
    assert not staged_wal_path.exists()
    assert not staged_path.with_name(".index.db.recover-shm").exists()


def test_recover_stale_wal_uses_staged_copy_before_atomic_swap(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "source.db"
    snapshot = tmp_path / "snapshot.db"

    conn = sqlite3.connect(source)
    apply_schema(conn)
    conn.execute("PRAGMA wal_autocheckpoint=0;")
    conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        ("/before", "[]", "[]", 1),
    )
    conn.commit()

    _make_recovery_snapshot(source, snapshot)
    conn.close()

    seen: dict[str, bool] = {"target_stale_before_swap": False}
    original_atomic_replace = atomic_replace_index

    def record_swap(staged_path: Path, target_path: Path) -> None:
        seen["target_stale_before_swap"] = has_stale_wal(target_path)
        original_atomic_replace(staged_path, target_path)

    monkeypatch.setattr("eodinga.index.storage.atomic_replace_index", record_swap)

    assert recover_stale_wal(snapshot) is True
    assert seen["target_stale_before_swap"] is True


def test_recover_stale_wal_does_not_publish_partial_stage_on_copy_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "index.db"
    conn = sqlite3.connect(path)
    apply_schema(conn)
    conn.close()
    path.with_name("index.db-wal").write_bytes(b"stale")

    staged = tmp_path / ".index.db.recover"
    partial = tmp_path / ".index.db.recover.partial"
    original_copy = shutil.copy2
    state = {"calls": 0}

    def flaky_copy(source: Path, destination: Path) -> Path:
        copied = original_copy(source, destination)
        state["calls"] += 1
        if Path(destination) == partial:
            raise OSError("simulated partial recovery copy failure")
        return Path(copied)

    monkeypatch.setattr(shutil, "copy2", flaky_copy)

    assert recover_stale_wal(path) is False
    assert state["calls"] >= 1
    assert not staged.exists()
    assert not partial.exists()
    assert not partial.with_name(".index.db.recover.partial-wal").exists()
    assert not partial.with_name(".index.db.recover.partial-shm").exists()


def test_recover_stale_wal_cleans_orphaned_partial_stage_before_retry(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    path = tmp_path / "index.db"
    conn = sqlite3.connect(source)
    apply_schema(conn)
    conn.execute("PRAGMA wal_autocheckpoint=0;")
    conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        ("/recovered", "[]", "[]", 1),
    )
    conn.commit()
    _make_recovery_snapshot(source, path)
    conn.close()

    partial = tmp_path / ".index.db.recover.partial"
    partial.write_bytes(b"orphaned")
    partial.with_name(".index.db.recover.partial-wal").write_bytes(b"orphaned")
    partial.with_name(".index.db.recover.partial-shm").write_bytes(b"orphaned")

    assert recover_stale_wal(path) is True
    assert not partial.exists()
    assert not partial.with_name(".index.db.recover.partial-wal").exists()
    assert not partial.with_name(".index.db.recover.partial-shm").exists()


def test_open_index_raises_when_stale_wal_recovery_fails(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "index.db"
    conn = sqlite3.connect(path)
    apply_schema(conn)
    conn.close()

    monkeypatch.setattr("eodinga.index.storage.has_stale_wal", lambda _path: True)
    monkeypatch.setattr("eodinga.index.storage.recover_stale_wal", lambda _path: False)

    with pytest.raises(RuntimeError, match="failed to recover stale WAL"):
        open_index(path)


def test_open_index_recovers_from_staged_copy_and_cleans_recovery_files(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    snapshot = tmp_path / "snapshot.db"

    conn = sqlite3.connect(source)
    apply_schema(conn)
    conn.execute("PRAGMA wal_autocheckpoint=0;")
    conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        ("/recovered-via-stage", "[]", "[]", 1),
    )
    conn.commit()

    _make_recovery_snapshot(source, snapshot)
    conn.close()

    reopened = open_index(snapshot)
    try:
        rows = reopened.execute("SELECT path FROM roots").fetchall()
        assert [str(row[0]) for row in rows] == ["/recovered-via-stage"]
    finally:
        reopened.close()

    staged_path = snapshot.with_name(".snapshot.db.recover")
    assert not staged_path.exists()
    assert not staged_path.with_name(".snapshot.db.recover-wal").exists()
    assert not staged_path.with_name(".snapshot.db.recover-shm").exists()


def test_recover_interrupted_recovery_swaps_existing_staged_database(tmp_path: Path) -> None:
    target = tmp_path / "index.db"
    staged = tmp_path / ".index.db.recover"

    target_conn = sqlite3.connect(target)
    apply_schema(target_conn)
    target_conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        ("/old", "[]", "[]", 1),
    )
    target_conn.commit()
    target_conn.close()

    staged_conn = sqlite3.connect(staged)
    apply_schema(staged_conn)
    staged_conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        ("/resumed", "[]", "[]", 1),
    )
    staged_conn.commit()
    staged_conn.close()

    assert recover_interrupted_recovery(target) is True
    assert _read_root_paths(target) == ["/resumed"]
    assert not staged.exists()


def test_recover_interrupted_recovery_rejects_uninitialized_stage(tmp_path: Path) -> None:
    target = tmp_path / "index.db"
    staged = tmp_path / ".index.db.recover"

    target_conn = sqlite3.connect(target)
    apply_schema(target_conn)
    target_conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        ("/live", "[]", "[]", 1),
    )
    target_conn.commit()
    target_conn.close()

    staged.write_bytes(b"")

    assert recover_interrupted_recovery(target) is False
    assert _read_root_paths(target) == ["/live"]
    assert not staged.exists()


def test_recover_interrupted_recovery_durably_cleans_rejected_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "index.db"
    staged = tmp_path / ".index.db.recover"

    target_conn = sqlite3.connect(target)
    apply_schema(target_conn)
    target_conn.close()
    staged.write_bytes(b"")
    calls: list[Path] = []

    monkeypatch.setattr("eodinga.index.storage._fsync_directory", lambda path: calls.append(path))

    assert recover_interrupted_recovery(target) is False
    assert calls == [tmp_path]
    assert not staged.exists()


def test_recover_interrupted_recovery_cleans_partial_stage_artifacts(tmp_path: Path) -> None:
    target = tmp_path / "index.db"
    staged = tmp_path / ".index.db.recover"
    partial = tmp_path / ".index.db.recover.partial"

    target_conn = sqlite3.connect(target)
    apply_schema(target_conn)
    target_conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        ("/old", "[]", "[]", 1),
    )
    target_conn.commit()
    target_conn.close()

    staged_conn = sqlite3.connect(staged)
    apply_schema(staged_conn)
    staged_conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        ("/resumed", "[]", "[]", 1),
    )
    staged_conn.commit()
    staged_conn.close()

    partial.write_bytes(b"orphaned")
    partial.with_name(".index.db.recover.partial-wal").write_bytes(b"orphaned")
    partial.with_name(".index.db.recover.partial-shm").write_bytes(b"orphaned")

    assert recover_interrupted_recovery(target) is True
    assert _read_root_paths(target) == ["/resumed"]
    assert not partial.exists()
    assert not partial.with_name(".index.db.recover.partial-wal").exists()
    assert not partial.with_name(".index.db.recover.partial-shm").exists()


def test_recover_interrupted_recovery_preserves_stage_when_swap_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "index.db"
    staged = tmp_path / ".index.db.recover"
    partial = tmp_path / ".index.db.recover.partial"

    target_conn = sqlite3.connect(target)
    apply_schema(target_conn)
    target_conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        ("/old", "[]", "[]", 1),
    )
    target_conn.commit()
    target_conn.close()

    staged_conn = sqlite3.connect(staged)
    apply_schema(staged_conn)
    staged_conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        ("/resumed", "[]", "[]", 1),
    )
    staged_conn.commit()
    staged_conn.close()

    partial.write_bytes(b"orphaned")
    partial.with_name(".index.db.recover.partial-wal").write_bytes(b"orphaned")
    partial.with_name(".index.db.recover.partial-shm").write_bytes(b"orphaned")

    def fail_swap(_staged: Path, _target: Path) -> None:
        raise OSError("simulated recovery swap failure")

    monkeypatch.setattr("eodinga.index.storage.atomic_replace_index", fail_swap)

    assert recover_interrupted_recovery(target) is False
    assert _read_root_paths(target) == ["/old"]
    assert staged.exists()
    assert _read_root_paths(staged) == ["/resumed"]
    assert not partial.exists()
    assert not partial.with_name(".index.db.recover.partial-wal").exists()
    assert not partial.with_name(".index.db.recover.partial-shm").exists()


def test_recover_interrupted_build_swaps_existing_staged_database(tmp_path: Path) -> None:
    target = tmp_path / "index.db"
    staged = tmp_path / ".index.db.next"

    target_conn = sqlite3.connect(target)
    apply_schema(target_conn)
    target_conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        ("/old", "[]", "[]", 1),
    )
    target_conn.commit()
    target_conn.close()

    staged_conn = sqlite3.connect(staged)
    apply_schema(staged_conn)
    staged_conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        ("/rebuilt", "[]", "[]", 1),
    )
    staged_conn.commit()
    staged_conn.close()
    _mark_staged_build_ready(staged)

    assert recover_interrupted_build(target) is True
    assert _read_root_paths(target) == ["/rebuilt"]
    assert not staged.exists()
    assert not staged.with_name(".index.db.next.ready").exists()


def test_recover_interrupted_build_cleans_partial_stage_artifacts(tmp_path: Path) -> None:
    target = tmp_path / "index.db"
    staged = tmp_path / ".index.db.next"
    partial = tmp_path / ".index.db.next.partial"

    target_conn = sqlite3.connect(target)
    apply_schema(target_conn)
    target_conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        ("/old", "[]", "[]", 1),
    )
    target_conn.commit()
    target_conn.close()

    staged_conn = sqlite3.connect(staged)
    apply_schema(staged_conn)
    staged_conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        ("/rebuilt", "[]", "[]", 1),
    )
    staged_conn.commit()
    staged_conn.close()
    _mark_staged_build_ready(staged)

    partial.write_bytes(b"orphaned")
    partial.with_name(".index.db.next.partial-wal").write_bytes(b"orphaned")
    partial.with_name(".index.db.next.partial-shm").write_bytes(b"orphaned")

    assert recover_interrupted_build(target) is True
    assert _read_root_paths(target) == ["/rebuilt"]
    assert not partial.exists()
    assert not partial.with_name(".index.db.next.partial-wal").exists()
    assert not partial.with_name(".index.db.next.partial-shm").exists()


def test_recover_interrupted_build_preserves_stage_when_swap_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "index.db"
    staged = tmp_path / ".index.db.next"
    partial = tmp_path / ".index.db.next.partial"

    target_conn = sqlite3.connect(target)
    apply_schema(target_conn)
    target_conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        ("/old", "[]", "[]", 1),
    )
    target_conn.commit()
    target_conn.close()

    staged_conn = sqlite3.connect(staged)
    apply_schema(staged_conn)
    staged_conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        ("/rebuilt", "[]", "[]", 1),
    )
    staged_conn.commit()
    staged_conn.close()
    _mark_staged_build_ready(staged)

    partial.write_bytes(b"orphaned")
    partial.with_name(".index.db.next.partial-wal").write_bytes(b"orphaned")
    partial.with_name(".index.db.next.partial-shm").write_bytes(b"orphaned")

    def fail_swap(_staged: Path, _target: Path) -> None:
        raise OSError("simulated staged-build swap failure")

    monkeypatch.setattr("eodinga.index.storage.atomic_replace_index", fail_swap)

    assert recover_interrupted_build(target) is False
    assert _read_root_paths(target) == ["/old"]
    assert staged.exists()
    assert _read_root_paths(staged) == ["/rebuilt"]
    assert staged.with_name(".index.db.next.ready").exists()
    assert not partial.exists()
    assert not partial.with_name(".index.db.next.partial-wal").exists()
    assert not partial.with_name(".index.db.next.partial-shm").exists()


def test_recover_interrupted_build_rejects_uninitialized_stage(tmp_path: Path) -> None:
    target = tmp_path / "index.db"
    staged = tmp_path / ".index.db.next"

    target_conn = sqlite3.connect(target)
    apply_schema(target_conn)
    target_conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        ("/live", "[]", "[]", 1),
    )
    target_conn.commit()
    target_conn.close()

    staged.write_bytes(b"")
    _mark_staged_build_ready(staged)

    assert recover_interrupted_build(target) is False
    assert _read_root_paths(target) == ["/live"]
    assert not staged.exists()
    assert not staged.with_name(".index.db.next.ready").exists()


def test_recover_interrupted_build_durably_cleans_rejected_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "index.db"
    staged = tmp_path / ".index.db.next"

    target_conn = sqlite3.connect(target)
    apply_schema(target_conn)
    target_conn.close()
    staged.write_bytes(b"")
    _mark_staged_build_ready(staged)
    calls: list[Path] = []

    monkeypatch.setattr("eodinga.index.storage._fsync_directory", lambda path: calls.append(path))

    assert recover_interrupted_build(target) is False
    assert calls == [tmp_path, tmp_path]
    assert not staged.exists()


def test_recover_interrupted_build_requires_completion_marker(tmp_path: Path) -> None:
    target = tmp_path / "index.db"
    staged = tmp_path / ".index.db.next"

    target_conn = sqlite3.connect(target)
    apply_schema(target_conn)
    target_conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        ("/live", "[]", "[]", 1),
    )
    target_conn.commit()
    target_conn.close()

    staged_conn = sqlite3.connect(staged)
    apply_schema(staged_conn)
    staged_conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        ("/partial", "[]", "[]", 1),
    )
    staged_conn.commit()
    staged_conn.close()

    assert has_resumable_interrupted_build(target) is False
    assert recover_interrupted_build(target) is False
    assert _read_root_paths(target) == ["/live"]
    assert staged.exists()


def test_discard_incomplete_interrupted_build_cleans_unmarked_stage(tmp_path: Path) -> None:
    target = tmp_path / "index.db"
    staged = tmp_path / ".index.db.next"

    staged_conn = sqlite3.connect(staged)
    apply_schema(staged_conn)
    staged_conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        ("/partial", "[]", "[]", 1),
    )
    staged_conn.commit()
    staged_conn.close()

    assert discard_incomplete_interrupted_build(target) is True
    assert not staged.exists()
    assert not staged.with_name(".index.db.next.ready").exists()


def test_open_index_resumes_interrupted_staged_build(tmp_path: Path) -> None:
    target = tmp_path / "index.db"
    staged = tmp_path / ".index.db.next"

    target_conn = sqlite3.connect(target)
    apply_schema(target_conn)
    target_conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        ("/old", "[]", "[]", 1),
    )
    target_conn.commit()
    target_conn.close()

    staged_conn = sqlite3.connect(staged)
    apply_schema(staged_conn)
    staged_conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        ("/rebuilt-startup", "[]", "[]", 1),
    )
    staged_conn.commit()
    staged_conn.close()
    _mark_staged_build_ready(staged)

    reopened = open_index(target)
    try:
        rows = reopened.execute("SELECT path FROM roots ORDER BY path").fetchall()
        assert [str(row[0]) for row in rows] == ["/rebuilt-startup"]
    finally:
        reopened.close()

    assert not staged.exists()
    assert not staged.with_name(".index.db.next-wal").exists()
    assert not staged.with_name(".index.db.next-shm").exists()
    assert not staged.with_name(".index.db.next.ready").exists()


def test_open_index_resumes_interrupted_recovery_with_staged_wal(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    target = tmp_path / "index.db"
    staged = tmp_path / ".index.db.recover"

    target_conn = sqlite3.connect(target)
    apply_schema(target_conn)
    target_conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        ("/old", "[]", "[]", 1),
    )
    target_conn.commit()
    target_conn.close()

    source_conn = sqlite3.connect(source)
    apply_schema(source_conn)
    source_conn.execute("PRAGMA wal_autocheckpoint=0;")
    source_conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        ("/resumed-from-wal", "[]", "[]", 1),
    )
    source_conn.commit()
    _make_recovery_snapshot(source, staged)
    source_conn.close()

    reopened = open_index(target)
    try:
        rows = reopened.execute("SELECT path FROM roots").fetchall()
        assert [str(row[0]) for row in rows] == ["/resumed-from-wal"]
    finally:
        reopened.close()

    assert not staged.exists()
    assert not staged.with_name(".index.db.recover-wal").exists()
    assert not staged.with_name(".index.db.recover-shm").exists()


def test_open_index_raises_when_interrupted_recovery_resume_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "index.db"
    staged = tmp_path / ".index.db.recover"
    staged.write_bytes(b"sqlite")

    monkeypatch.setattr("eodinga.index.storage.recover_interrupted_recovery", lambda _path: False)

    with pytest.raises(RuntimeError, match="failed to resume interrupted recovery"):
        open_index(path)


def test_open_index_raises_when_interrupted_build_resume_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "index.db"
    staged = tmp_path / ".index.db.next"
    staged.write_bytes(b"sqlite")
    _mark_staged_build_ready(staged)

    monkeypatch.setattr("eodinga.index.storage.recover_interrupted_build", lambda _path: False)

    with pytest.raises(RuntimeError, match="failed to resume interrupted staged build"):
        open_index(path)


def test_open_index_cleans_orphaned_recovery_sidecars_before_open(tmp_path: Path) -> None:
    path = tmp_path / "index.db"
    staged = tmp_path / ".index.db.recover"
    staged.with_name(".index.db.recover-wal").write_bytes(b"orphaned")
    staged.with_name(".index.db.recover-shm").write_bytes(b"orphaned")

    reopened = open_index(path)
    try:
        rows = reopened.execute("SELECT COUNT(*) FROM roots").fetchone()
        assert rows is not None
        assert int(rows[0]) == 0
    finally:
        reopened.close()

    assert not staged.exists()
    assert not staged.with_name(".index.db.recover-wal").exists()
    assert not staged.with_name(".index.db.recover-shm").exists()


def test_open_index_cleans_orphaned_live_sidecars_before_open(tmp_path: Path) -> None:
    path = tmp_path / "index.db"
    path.with_name("index.db-wal").write_bytes(b"orphaned")
    path.with_name("index.db-shm").write_bytes(b"orphaned")

    reopened = open_index(path)
    try:
        rows = reopened.execute("SELECT COUNT(*) FROM roots").fetchone()
        assert rows is not None
        assert int(rows[0]) == 0
    finally:
        reopened.close()

    assert not path.with_name("index.db-wal").exists()
    assert not path.with_name("index.db-shm").exists()


def test_open_index_cleans_partial_recovery_copy_before_open(tmp_path: Path) -> None:
    path = tmp_path / "index.db"
    partial = tmp_path / ".index.db.recover.partial"
    partial.write_bytes(b"sqlite")
    partial.with_name(".index.db.recover.partial-wal").write_bytes(b"orphaned")
    partial.with_name(".index.db.recover.partial-shm").write_bytes(b"orphaned")

    reopened = open_index(path)
    try:
        rows = reopened.execute("SELECT COUNT(*) FROM roots").fetchone()
        assert rows is not None
        assert int(rows[0]) == 0
    finally:
        reopened.close()

    assert not partial.exists()
    assert not partial.with_name(".index.db.recover.partial-wal").exists()
    assert not partial.with_name(".index.db.recover.partial-shm").exists()


def test_open_index_cleans_orphaned_build_sidecars_before_open(tmp_path: Path) -> None:
    path = tmp_path / "index.db"
    staged = tmp_path / ".index.db.next"
    staged.with_name(".index.db.next-wal").write_bytes(b"orphaned")
    staged.with_name(".index.db.next-shm").write_bytes(b"orphaned")

    reopened = open_index(path)
    try:
        rows = reopened.execute("SELECT COUNT(*) FROM roots").fetchone()
        assert rows is not None
        assert int(rows[0]) == 0
    finally:
        reopened.close()

    assert not staged.exists()
    assert not staged.with_name(".index.db.next-wal").exists()
    assert not staged.with_name(".index.db.next-shm").exists()


def test_open_index_discards_incomplete_interrupted_build_without_marker(tmp_path: Path) -> None:
    target = tmp_path / "index.db"
    staged = tmp_path / ".index.db.next"

    target_conn = sqlite3.connect(target)
    apply_schema(target_conn)
    target_conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        ("/live", "[]", "[]", 1),
    )
    target_conn.commit()
    target_conn.close()

    staged_conn = sqlite3.connect(staged)
    apply_schema(staged_conn)
    staged_conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        ("/partial", "[]", "[]", 1),
    )
    staged_conn.commit()
    staged_conn.close()

    reopened = open_index(target)
    try:
        rows = reopened.execute("SELECT path FROM roots ORDER BY path").fetchall()
        assert [str(row[0]) for row in rows] == ["/live"]
    finally:
        reopened.close()

    assert not staged.exists()
    assert not staged.with_name(".index.db.next.ready").exists()


def test_open_index_cleans_partial_build_copy_before_open(tmp_path: Path) -> None:
    path = tmp_path / "index.db"
    partial = tmp_path / ".index.db.next.partial"
    partial.write_bytes(b"sqlite")
    partial.with_name(".index.db.next.partial-wal").write_bytes(b"orphaned")
    partial.with_name(".index.db.next.partial-shm").write_bytes(b"orphaned")

    reopened = open_index(path)
    try:
        rows = reopened.execute("SELECT COUNT(*) FROM roots").fetchone()
        assert rows is not None
        assert int(rows[0]) == 0
    finally:
        reopened.close()

    assert not partial.exists()
    assert not partial.with_name(".index.db.next.partial-wal").exists()
    assert not partial.with_name(".index.db.next.partial-shm").exists()


def test_open_index_cleans_orphaned_build_marker_before_open(tmp_path: Path) -> None:
    path = tmp_path / "index.db"
    staged = tmp_path / ".index.db.next"
    staged.with_name(".index.db.next.ready").write_text("ready\n", encoding="utf-8")

    reopened = open_index(path)
    reopened.close()

    assert not staged.exists()
    assert not staged.with_name(".index.db.next.ready").exists()


def test_open_index_fsyncs_parent_directory_after_cleaning_startup_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "index.db"
    path.with_name("index.db-wal").write_bytes(b"orphaned")
    partial = tmp_path / ".index.db.recover.partial"
    partial.write_bytes(b"sqlite")
    partial.with_name(".index.db.recover.partial-wal").write_bytes(b"orphaned")
    partial.with_name(".index.db.recover.partial-shm").write_bytes(b"orphaned")

    calls: list[Path] = []
    original_fsync_directory = storage_module._fsync_directory

    def record_directory(directory: Path) -> None:
        calls.append(directory)
        original_fsync_directory(directory)

    monkeypatch.setattr("eodinga.index.storage._fsync_directory", record_directory)

    reopened = open_index(path)
    reopened.close()

    assert calls == [tmp_path, tmp_path]


def test_open_index_skips_parent_fsync_when_no_startup_artifacts_need_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "index.db"
    calls: list[Path] = []

    def record_directory(directory: Path) -> None:
        calls.append(directory)

    monkeypatch.setattr("eodinga.index.storage._fsync_directory", record_directory)

    reopened = open_index(path)
    reopened.close()

    assert calls == []
