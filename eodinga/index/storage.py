from __future__ import annotations

import os
import sqlite3
import shutil
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import NamedTuple

from eodinga.index.migrations import migrate
from eodinga.index.schema import PRAGMAS, current_schema_version
from eodinga.observability import get_logger

SQLITE_CACHED_STATEMENTS = 128
_ACTIVE_PRAGMA_OVERRIDES: dict[int, dict[str, str]] = {}
_PRAGMA_VALUE_ALIASES: dict[str, dict[str, str]] = {
    "synchronous": {
        "OFF": "0",
        "NORMAL": "1",
        "FULL": "2",
        "EXTRA": "3",
    }
}


class _PragmaRestore(NamedTuple):
    name: str
    value: str
    was_active: bool


def _read_pragma(conn: sqlite3.Connection, name: str) -> str:
    row = conn.execute(f"PRAGMA {name};").fetchone()
    if row is None:
        raise sqlite3.OperationalError(f"PRAGMA {name} did not return a value")
    return str(row[0])


def _sidecar(path: Path, suffix: str) -> Path:
    return path.with_name(f"{path.name}{suffix}")


def _pragma_matches(name: str, current_value: str, requested_value: str) -> bool:
    if current_value == requested_value:
        return True
    aliases = _PRAGMA_VALUE_ALIASES.get(name)
    if aliases is None:
        return False
    return aliases.get(requested_value.upper()) == current_value


def configure_connection(
    conn: sqlite3.Connection, *, row_factory: type[sqlite3.Row] | None = sqlite3.Row
) -> sqlite3.Connection:
    if row_factory is not None:
        conn.row_factory = row_factory
    for pragma in PRAGMAS:
        conn.execute(pragma)
    return conn


def connect_database(
    path: Path, *, row_factory: type[sqlite3.Row] | None = sqlite3.Row
) -> sqlite3.Connection:
    return configure_connection(
        sqlite3.connect(path, cached_statements=SQLITE_CACHED_STATEMENTS),
        row_factory=row_factory,
    )


@contextmanager
def temporary_pragmas(
    conn: sqlite3.Connection,
    overrides: Mapping[str, str | int],
) -> Iterator[None]:
    if conn.in_transaction or not overrides:
        yield
        return
    connection_id = id(conn)
    active = _ACTIVE_PRAGMA_OVERRIDES.setdefault(connection_id, {})
    restore: list[_PragmaRestore] = []
    for name, value in overrides.items():
        requested_value = str(value)
        active_value = active.get(name)
        if active_value is not None:
            if _pragma_matches(name, active_value, requested_value):
                continue
            restore.append(_PragmaRestore(name=name, value=active_value, was_active=True))
            conn.execute(f"PRAGMA {name}={value};")
            active[name] = requested_value
            continue
        current_value = _read_pragma(conn, name)
        if _pragma_matches(name, current_value, requested_value):
            continue
        restore.append(_PragmaRestore(name=name, value=current_value, was_active=False))
        conn.execute(f"PRAGMA {name}={value};")
        active[name] = requested_value
    try:
        yield
    finally:
        for entry in reversed(restore):
            conn.execute(f"PRAGMA {entry.name}={entry.value};")
            if entry.was_active:
                active[entry.name] = entry.value
            else:
                active.pop(entry.name, None)
        if not active:
            _ACTIVE_PRAGMA_OVERRIDES.pop(connection_id, None)


def _checkpoint_wal(path: Path) -> None:
    if not path.exists():
        return
    conn = connect_database(path)
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE);").fetchall()
    finally:
        conn.close()


def _cleanup_sidecars(path: Path) -> bool:
    cleaned = False
    for suffix in ("-wal", "-shm"):
        sidecar = _sidecar(path, suffix)
        if sidecar.exists():
            sidecar.unlink()
            cleaned = True
    return cleaned


def _cleanup_index_files(path: Path, *, durable: bool = False) -> bool:
    cleaned = False
    if path.exists():
        path.unlink()
        cleaned = True
    cleaned = _cleanup_sidecars(path) or cleaned
    if cleaned and durable:
        _fsync_directory(path.parent)
    return cleaned


def _fsync_file(path: Path) -> None:
    if not path.exists():
        return
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _fsync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def has_stale_wal(path: Path) -> bool:
    wal_path = _sidecar(path, "-wal")
    return path.exists() and wal_path.exists() and wal_path.stat().st_size > 0


def _staged_recovery_path(path: Path) -> Path:
    return path.with_name(f".{path.name}.recover")


def _staged_build_path(path: Path) -> Path:
    return path.with_name(f".{path.name}.next")


def _staged_build_marker_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.ready")


def _partial_copy_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.partial")


def _cleanup_orphan_recovery_sidecars(path: Path, *, durable: bool = False) -> bool:
    staged_path = _staged_recovery_path(path)
    if staged_path.exists():
        return False
    cleaned = False
    for suffix in ("-wal", "-shm"):
        orphan = _sidecar(staged_path, suffix)
        if orphan.exists():
            orphan.unlink()
            cleaned = True
    if cleaned and durable:
        _fsync_directory(path.parent)
    return cleaned


def _cleanup_partial_copy_artifacts(path: Path, *, durable: bool = False) -> bool:
    partial_path = _partial_copy_path(path)
    return _cleanup_index_files(partial_path, durable=durable)


def _cleanup_orphan_build_sidecars(path: Path, *, durable: bool = False) -> bool:
    staged_path = _staged_build_path(path)
    if staged_path.exists():
        return False
    cleaned = False
    for suffix in ("-wal", "-shm"):
        orphan = _sidecar(staged_path, suffix)
        if orphan.exists():
            orphan.unlink()
            cleaned = True
    if cleaned and durable:
        _fsync_directory(path.parent)
    return cleaned


def _cleanup_orphan_build_marker(path: Path, *, durable: bool = False) -> bool:
    staged_path = _staged_build_path(path)
    if staged_path.exists():
        return False
    return _cleanup_build_marker(staged_path, durable=durable)


def _cleanup_build_marker(path: Path, *, durable: bool = False) -> bool:
    marker_path = _staged_build_marker_path(path)
    if not marker_path.exists():
        return False
    marker_path.unlink()
    if durable:
        _fsync_directory(marker_path.parent)
    return True


def _cleanup_orphan_live_sidecars(path: Path, *, durable: bool = False) -> bool:
    if path.exists():
        return False
    cleaned = _cleanup_sidecars(path)
    if cleaned and durable:
        _fsync_directory(path.parent)
    return cleaned


def has_resumable_interrupted_build(path: Path) -> bool:
    staged_path = _staged_build_path(path)
    return staged_path.exists() and _staged_build_marker_path(staged_path).exists()


def mark_build_stage_complete(staged_path: Path) -> None:
    marker_path = _staged_build_marker_path(staged_path)
    marker_path.write_text("ready\n", encoding="utf-8")
    try:
        _fsync_file(marker_path)
        _fsync_directory(marker_path.parent)
    except Exception:
        _cleanup_build_marker(staged_path, durable=True)
        raise


def discard_incomplete_interrupted_build(path: Path) -> bool:
    staged_path = _staged_build_path(path)
    if not staged_path.exists() or has_resumable_interrupted_build(path):
        return False
    logger = get_logger("index.storage")
    logger.warning("discarding incomplete staged build for {}", path)
    _cleanup_index_files(staged_path, durable=True)
    _cleanup_partial_copy_artifacts(staged_path, durable=True)
    _cleanup_build_marker(staged_path, durable=True)
    return True


def _copy_index_with_sidecars(source_path: Path, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    partial_path = _partial_copy_path(target_path)
    _cleanup_index_files(target_path)
    _cleanup_index_files(partial_path)
    try:
        shutil.copy2(source_path, partial_path)
        _fsync_file(partial_path)
        for suffix in ("-wal", "-shm"):
            sidecar = _sidecar(source_path, suffix)
            if sidecar.exists():
                partial_sidecar = _sidecar(partial_path, suffix)
                shutil.copy2(sidecar, partial_sidecar)
                _fsync_file(partial_sidecar)
        _fsync_directory(target_path.parent)
        os.replace(partial_path, target_path)
        for suffix in ("-wal", "-shm"):
            partial_sidecar = _sidecar(partial_path, suffix)
            if partial_sidecar.exists():
                target_sidecar = _sidecar(target_path, suffix)
                os.replace(partial_sidecar, target_sidecar)
                _fsync_file(target_sidecar)
        _fsync_file(target_path)
        _fsync_directory(target_path.parent)
    except Exception:
        _cleanup_index_files(partial_path)
        raise


def _replay_stale_wal(path: Path) -> bool:
    conn = connect_database(path)
    try:
        migrate(conn)
    finally:
        conn.close()
    _checkpoint_wal(path)
    for suffix in ("-wal", "-shm"):
        sidecar = _sidecar(path, suffix)
        if sidecar.exists() and sidecar.stat().st_size > 0:
            return False
        if sidecar.exists():
            sidecar.unlink()
    return True


def _has_initialized_schema(path: Path) -> bool:
    conn = connect_database(path)
    try:
        return current_schema_version(conn) > 0
    finally:
        conn.close()


def recover_stale_wal(path: Path) -> bool:
    if not has_stale_wal(path):
        return False
    logger = get_logger("index.storage")
    logger.warning("recovering stale WAL for {}", path)
    staged_path = _staged_recovery_path(path)
    _cleanup_partial_copy_artifacts(staged_path)
    try:
        _copy_index_with_sidecars(path, staged_path)
        if not _replay_stale_wal(staged_path):
            return False
        atomic_replace_index(staged_path, path)
    except (OSError, sqlite3.DatabaseError):
        logger.exception("failed staged stale WAL recovery for {}", path)
        return False
    finally:
        _cleanup_index_files(staged_path, durable=True)
        _cleanup_index_files(_partial_copy_path(staged_path), durable=True)
    return not has_stale_wal(path)


def recover_interrupted_recovery(path: Path) -> bool:
    staged_path = _staged_recovery_path(path)
    if not staged_path.exists():
        return False
    logger = get_logger("index.storage")
    logger.warning("resuming interrupted recovery for {}", path)
    try:
        if has_stale_wal(staged_path) and not _replay_stale_wal(staged_path):
            _cleanup_index_files(staged_path, durable=True)
            _cleanup_partial_copy_artifacts(staged_path)
            return False
        if not _has_initialized_schema(staged_path):
            logger.warning("skipping interrupted recovery swap with uninitialized stage {}", staged_path)
            _cleanup_index_files(staged_path, durable=True)
            _cleanup_partial_copy_artifacts(staged_path)
            return False
    except (OSError, sqlite3.DatabaseError):
        logger.exception("failed interrupted recovery preparation for {}", path)
        _cleanup_index_files(staged_path, durable=True)
        _cleanup_partial_copy_artifacts(staged_path)
        return False
    try:
        atomic_replace_index(staged_path, path)
    except (OSError, sqlite3.DatabaseError):
        logger.exception("failed interrupted recovery swap for {}", path)
        _cleanup_partial_copy_artifacts(staged_path)
        return False
    _cleanup_index_files(staged_path, durable=True)
    _cleanup_partial_copy_artifacts(staged_path)
    return path.exists() and not staged_path.exists() and not has_stale_wal(path)


def recover_interrupted_build(path: Path) -> bool:
    staged_path = _staged_build_path(path)
    if not has_resumable_interrupted_build(path):
        return False
    logger = get_logger("index.storage")
    logger.warning("resuming interrupted staged build for {}", path)
    try:
        if has_stale_wal(staged_path) and not _replay_stale_wal(staged_path):
            _cleanup_index_files(staged_path, durable=True)
            _cleanup_partial_copy_artifacts(staged_path)
            _cleanup_build_marker(staged_path, durable=True)
            return False
        if not _has_initialized_schema(staged_path):
            logger.warning("skipping interrupted staged build swap with uninitialized stage {}", staged_path)
            _cleanup_index_files(staged_path, durable=True)
            _cleanup_partial_copy_artifacts(staged_path)
            _cleanup_build_marker(staged_path, durable=True)
            return False
    except (OSError, sqlite3.DatabaseError):
        logger.exception("failed interrupted staged build preparation for {}", path)
        _cleanup_index_files(staged_path, durable=True)
        _cleanup_partial_copy_artifacts(staged_path)
        _cleanup_build_marker(staged_path, durable=True)
        return False
    try:
        atomic_replace_index(staged_path, path)
    except (OSError, sqlite3.DatabaseError):
        logger.exception("failed interrupted staged build swap for {}", path)
        _cleanup_partial_copy_artifacts(staged_path)
        return False
    _cleanup_index_files(staged_path, durable=True)
    _cleanup_partial_copy_artifacts(staged_path)
    _cleanup_build_marker(staged_path, durable=True)
    return path.exists() and not staged_path.exists() and not has_stale_wal(path)


def open_index(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    _cleanup_partial_copy_artifacts(_staged_recovery_path(path), durable=True)
    _cleanup_partial_copy_artifacts(_staged_build_path(path), durable=True)
    _cleanup_orphan_live_sidecars(path, durable=True)
    _cleanup_orphan_recovery_sidecars(path, durable=True)
    _cleanup_orphan_build_sidecars(path, durable=True)
    _cleanup_orphan_build_marker(path, durable=True)
    recovery_staged = _staged_recovery_path(path).exists()
    if recovery_staged and not recover_interrupted_recovery(path):
        raise RuntimeError(f"failed to resume interrupted recovery for {path}")
    build_staged = _staged_build_path(path).exists()
    if build_staged:
        if has_resumable_interrupted_build(path):
            if not recover_interrupted_build(path):
                raise RuntimeError(f"failed to resume interrupted staged build for {path}")
        else:
            discard_incomplete_interrupted_build(path)
    if has_stale_wal(path) and not recover_stale_wal(path):
        raise RuntimeError(f"failed to recover stale WAL for {path}")
    conn = connect_database(path)
    migrate(conn)
    return conn


def atomic_replace_index(staged_path: Path, target_path: Path) -> None:
    if not staged_path.exists():
        raise FileNotFoundError(staged_path)
    target_dir = target_path.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    _checkpoint_wal(staged_path)
    _fsync_file(staged_path)
    _fsync_directory(target_dir)
    os.replace(staged_path, target_path)
    _fsync_file(target_path)
    _cleanup_sidecars(target_path)
    _cleanup_sidecars(staged_path)
    _fsync_directory(target_dir)


__all__ = [
    "atomic_replace_index",
    "configure_connection",
    "connect_database",
    "discard_incomplete_interrupted_build",
    "has_stale_wal",
    "has_resumable_interrupted_build",
    "mark_build_stage_complete",
    "open_index",
    "recover_interrupted_build",
    "recover_interrupted_recovery",
    "recover_stale_wal",
]
