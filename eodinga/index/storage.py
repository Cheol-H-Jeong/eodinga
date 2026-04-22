from __future__ import annotations

import os
import sqlite3
import shutil
from pathlib import Path

from eodinga.index.migrations import migrate
from eodinga.index.schema import PRAGMAS
from eodinga.observability import get_logger


def _sidecar(path: Path, suffix: str) -> Path:
    return path.with_name(f"{path.name}{suffix}")


def _configure_connection(conn: sqlite3.Connection) -> sqlite3.Connection:
    conn.row_factory = sqlite3.Row
    for pragma in PRAGMAS:
        conn.execute(pragma)
    return conn


def _checkpoint_wal(path: Path) -> None:
    if not path.exists():
        return
    conn = _configure_connection(sqlite3.connect(path))
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE);").fetchall()
    finally:
        conn.close()


def _cleanup_sidecars(path: Path) -> None:
    for suffix in ("-wal", "-shm"):
        sidecar = _sidecar(path, suffix)
        if sidecar.exists():
            sidecar.unlink()


def _cleanup_index_files(path: Path) -> None:
    if path.exists():
        path.unlink()
    _cleanup_sidecars(path)


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


def _cleanup_orphan_recovery_sidecars(path: Path) -> bool:
    staged_path = _staged_recovery_path(path)
    if staged_path.exists():
        return False
    cleaned = False
    for suffix in ("-wal", "-shm"):
        orphan = _sidecar(staged_path, suffix)
        if orphan.exists():
            orphan.unlink()
            cleaned = True
    return cleaned


def _copy_index_with_sidecars(source_path: Path, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    _cleanup_index_files(target_path)
    shutil.copy2(source_path, target_path)
    for suffix in ("-wal", "-shm"):
        sidecar = _sidecar(source_path, suffix)
        if sidecar.exists():
            shutil.copy2(sidecar, _sidecar(target_path, suffix))


def _replay_stale_wal(path: Path) -> bool:
    conn = _configure_connection(sqlite3.connect(path))
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


def recover_stale_wal(path: Path) -> bool:
    if not has_stale_wal(path):
        return False
    logger = get_logger("index.storage")
    logger.warning("recovering stale WAL for {}", path)
    staged_path = _staged_recovery_path(path)
    try:
        _copy_index_with_sidecars(path, staged_path)
        if not _replay_stale_wal(staged_path):
            return False
        atomic_replace_index(staged_path, path)
    except (OSError, sqlite3.DatabaseError):
        logger.exception("failed staged stale WAL recovery for {}", path)
        return False
    finally:
        _cleanup_index_files(staged_path)
    return not has_stale_wal(path)


def recover_interrupted_recovery(path: Path) -> bool:
    staged_path = _staged_recovery_path(path)
    if not staged_path.exists():
        return False
    logger = get_logger("index.storage")
    logger.warning("resuming interrupted recovery for {}", path)
    try:
        if has_stale_wal(staged_path) and not _replay_stale_wal(staged_path):
            return False
        atomic_replace_index(staged_path, path)
    except (OSError, sqlite3.DatabaseError):
        logger.exception("failed interrupted recovery resume for {}", path)
        return False
    finally:
        _cleanup_index_files(staged_path)
    return path.exists() and not staged_path.exists() and not has_stale_wal(path)


def open_index(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    _cleanup_orphan_recovery_sidecars(path)
    if recover_interrupted_recovery(path):
        pass
    if has_stale_wal(path) and not recover_stale_wal(path):
        raise RuntimeError(f"failed to recover stale WAL for {path}")
    conn = _configure_connection(sqlite3.connect(path))
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
    "has_stale_wal",
    "open_index",
    "recover_interrupted_recovery",
    "recover_stale_wal",
]
