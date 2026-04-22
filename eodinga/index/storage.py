from __future__ import annotations

import os
import sqlite3
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


def has_stale_wal(path: Path) -> bool:
    wal_path = _sidecar(path, "-wal")
    return path.exists() and wal_path.exists() and wal_path.stat().st_size > 0


def recover_stale_wal(path: Path) -> bool:
    if not has_stale_wal(path):
        return False
    logger = get_logger("index.storage")
    logger.warning("recovering stale WAL for {}", path)
    conn = _configure_connection(sqlite3.connect(path))
    try:
        migrate(conn)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE);").fetchall()
    finally:
        conn.close()
    wal_path = _sidecar(path, "-wal")
    return not wal_path.exists() or wal_path.stat().st_size == 0


def open_index(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    recover_stale_wal(path)
    conn = _configure_connection(sqlite3.connect(path))
    migrate(conn)
    return conn


def atomic_replace_index(staged_path: Path, target_path: Path) -> None:
    if not staged_path.exists():
        raise FileNotFoundError(staged_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    for suffix in ("-wal", "-shm"):
        sidecar = _sidecar(target_path, suffix)
        if sidecar.exists():
            sidecar.unlink()

    os.replace(staged_path, target_path)
    for suffix in ("-wal", "-shm"):
        staged_sidecar = _sidecar(staged_path, suffix)
        target_sidecar = _sidecar(target_path, suffix)
        if staged_sidecar.exists():
            os.replace(staged_sidecar, target_sidecar)


__all__ = [
    "atomic_replace_index",
    "has_stale_wal",
    "open_index",
    "recover_stale_wal",
]
