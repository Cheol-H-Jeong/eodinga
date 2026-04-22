from __future__ import annotations

import sqlite3

from eodinga.index.schema import SCHEMA_VERSION, apply_schema, current_schema_version


def migrate(conn: sqlite3.Connection, target: int | None = None) -> int:
    desired = target or SCHEMA_VERSION
    version = current_schema_version(conn)
    if version == 0 and desired >= 1:
        apply_schema(conn)
        version = 1
    if version != desired:
        raise ValueError(f"unsupported migration target: {desired}")
    return version
