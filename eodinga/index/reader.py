from __future__ import annotations

import sqlite3
from pathlib import Path

from eodinga.common import FileRecord, IndexStats


def find_by_path(conn: sqlite3.Connection, path: Path) -> FileRecord | None:
    row = conn.execute(
        """
        SELECT id, root_id, path, parent_path, name, name_lower, ext, size, mtime, ctime,
               is_dir, is_symlink, content_hash, indexed_at
        FROM files WHERE path = ?
        """,
        (str(path),),
    ).fetchone()
    if row is None:
        return None
    return FileRecord(
        id=int(row[0]),
        root_id=int(row[1]),
        path=Path(row[2]),
        parent_path=Path(row[3]),
        name=str(row[4]),
        name_lower=str(row[5]),
        ext=str(row[6]),
        size=int(row[7]),
        mtime=int(row[8]),
        ctime=int(row[9]),
        is_dir=bool(row[10]),
        is_symlink=bool(row[11]),
        content_hash=row[12],
        indexed_at=int(row[13]),
    )


def stats(conn: sqlite3.Connection) -> IndexStats:
    row = conn.execute(
        """
        SELECT
          COUNT(*) AS file_count,
          SUM(CASE WHEN is_dir = 1 THEN 1 ELSE 0 END) AS dir_count,
          COALESCE(SUM(size), 0) AS total_size
        FROM files
        """
    ).fetchone()
    content_count = int(conn.execute("SELECT COUNT(*) FROM content_map").fetchone()[0])
    roots = tuple(Path(value[0]) for value in conn.execute("SELECT path FROM roots ORDER BY path"))
    return IndexStats(
        file_count=int(row[0]),
        dir_count=int(row[1] or 0),
        content_count=content_count,
        total_size=int(row[2] or 0),
        roots=roots,
    )


def list_roots(conn: sqlite3.Connection) -> list[Path]:
    rows = conn.execute("SELECT path FROM roots WHERE enabled = 1 ORDER BY path")
    return [Path(row[0]) for row in rows]
