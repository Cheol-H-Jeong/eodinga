from __future__ import annotations

import os
import sqlite3
import shutil
from pathlib import Path

from eodinga.index.migrations import migrate
from eodinga.index.schema import PRAGMAS
from eodinga.observability import get_logger

SQLITE_CACHED_STATEMENTS = 128
SQLITE_TIMEOUT_SECONDS = 5.0


def _sidecar(path: Path, suffix: str) -> Path:
    return path.with_name(f"{path.name}{suffix}")


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
        sqlite3.connect(
            path,
            cached_statements=SQLITE_CACHED_STATEMENTS,
            timeout=SQLITE_TIMEOUT_SECONDS,
        ),
        row_factory=row_factory,
    )


def _checkpoint_wal(path: Path) -> None:
    if not path.exists():
        return
    conn = connect_database(path)
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


def _staged_build_path(path: Path) -> Path:
    return path.with_name(f".{path.name}.next")


def _staged_ready_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.ready")


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
    ready_path = _staged_ready_path(staged_path)
    if ready_path.exists():
        ready_path.unlink()
        cleaned = True
    return cleaned


def _cleanup_orphan_build_sidecars(path: Path) -> bool:
    staged_path = _staged_build_path(path)
    if staged_path.exists():
        return False
    cleaned = False
    for suffix in ("-wal", "-shm"):
        orphan = _sidecar(staged_path, suffix)
        if orphan.exists():
            orphan.unlink()
            cleaned = True
    ready_path = _staged_ready_path(staged_path)
    if ready_path.exists():
        ready_path.unlink()
        cleaned = True
    return cleaned


def _cleanup_staged_artifacts(path: Path) -> None:
    _cleanup_index_files(path)
    ready_path = _staged_ready_path(path)
    if ready_path.exists():
        ready_path.unlink()


def _mark_staged_ready(path: Path) -> None:
    ready_path = _staged_ready_path(path)
    temp_path = ready_path.with_name(f".{ready_path.name}.tmp")
    if temp_path.exists():
        temp_path.unlink()
    try:
        temp_path.write_text("ready\n", encoding="utf-8")
        _fsync_file(temp_path)
        os.replace(temp_path, ready_path)
        _fsync_file(ready_path)
        _fsync_directory(path.parent)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise


def _is_staged_ready(path: Path) -> bool:
    return path.exists() and _staged_ready_path(path).exists()


def _copy_index_with_sidecars(source_path: Path, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    _cleanup_index_files(target_path)
    shutil.copy2(source_path, target_path)
    for suffix in ("-wal", "-shm"):
        sidecar = _sidecar(source_path, suffix)
        if sidecar.exists():
            shutil.copy2(sidecar, _sidecar(target_path, suffix))


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
        _mark_staged_ready(staged_path)
        atomic_replace_index(staged_path, path)
    except (OSError, sqlite3.DatabaseError):
        logger.exception("failed staged stale WAL recovery for {}", path)
        return False
    finally:
        _cleanup_staged_artifacts(staged_path)
    return not has_stale_wal(path)


def recover_interrupted_recovery(path: Path) -> bool:
    staged_path = _staged_recovery_path(path)
    if not staged_path.exists():
        return False
    logger = get_logger("index.storage")
    if not _is_staged_ready(staged_path):
        logger.warning("discarding incomplete staged recovery for {}", path)
        _cleanup_staged_artifacts(staged_path)
        return False
    logger.warning("resuming interrupted recovery for {}", path)
    try:
        if has_stale_wal(staged_path) and not _replay_stale_wal(staged_path):
            return False
        atomic_replace_index(staged_path, path)
    except (OSError, sqlite3.DatabaseError):
        logger.exception("failed interrupted recovery resume for {}", path)
        return False
    finally:
        _cleanup_staged_artifacts(staged_path)
    return path.exists() and not staged_path.exists() and not has_stale_wal(path)


def recover_interrupted_build(path: Path) -> bool:
    staged_path = _staged_build_path(path)
    if not staged_path.exists():
        return False
    logger = get_logger("index.storage")
    if not _is_staged_ready(staged_path):
        logger.warning("discarding incomplete staged build for {}", path)
        _cleanup_staged_artifacts(staged_path)
        return False
    logger.warning("resuming interrupted staged build for {}", path)
    try:
        if has_stale_wal(staged_path) and not _replay_stale_wal(staged_path):
            return False
        atomic_replace_index(staged_path, path)
    except (OSError, sqlite3.DatabaseError):
        logger.exception("failed interrupted staged build resume for {}", path)
        return False
    finally:
        _cleanup_staged_artifacts(staged_path)
    return path.exists() and not staged_path.exists() and not has_stale_wal(path)


def open_index(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    _cleanup_orphan_recovery_sidecars(path)
    _cleanup_orphan_build_sidecars(path)
    recovery_staged_path = _staged_recovery_path(path)
    build_staged_path = _staged_build_path(path)
    recovery_staged = _is_staged_ready(recovery_staged_path)
    if recovery_staged and not recover_interrupted_recovery(path):
        raise RuntimeError(f"failed to resume interrupted recovery for {path}")
    build_staged = _is_staged_ready(build_staged_path)
    if build_staged and not recover_interrupted_build(path):
        raise RuntimeError(f"failed to resume interrupted staged build for {path}")
    if recovery_staged_path.exists() and not recovery_staged:
        _cleanup_staged_artifacts(recovery_staged_path)
    if build_staged_path.exists() and not build_staged:
        _cleanup_staged_artifacts(build_staged_path)
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
    "SQLITE_CACHED_STATEMENTS",
    "SQLITE_TIMEOUT_SECONDS",
    "atomic_replace_index",
    "configure_connection",
    "connect_database",
    "has_stale_wal",
    "open_index",
    "recover_interrupted_build",
    "recover_interrupted_recovery",
    "recover_stale_wal",
]
