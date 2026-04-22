from __future__ import annotations

import sqlite3

from eodinga.index.schema import SCHEMA_VERSION, apply_schema, current_schema_version


def _set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(
        "INSERT INTO meta(key, value) VALUES('schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(version),),
    )


def migrate(conn: sqlite3.Connection, target: int | None = None) -> int:
    desired = target or SCHEMA_VERSION
    version = current_schema_version(conn)
    if version == 0 and desired >= 1:
        apply_schema(conn)
        version = 2
    if version == 1 and desired >= 2:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_files_content_hash ON files(content_hash)")
        _set_schema_version(conn, 2)
        conn.commit()
        version = 2
    if version != desired:
        raise ValueError(f"unsupported migration target: {desired}")
    return version
