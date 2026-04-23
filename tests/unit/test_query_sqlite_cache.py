from __future__ import annotations

import sqlite3
from typing import cast

from eodinga.query.sqlite_cache import PreparedStatementCache, clear_statement_cache, statement_cache_for


class RecordingCursor(sqlite3.Cursor):
    def close(self) -> None:
        connection = cast(RecordingConnection, self.connection)
        connection.closed_cursors += 1
        super().close()


class RecordingConnection(sqlite3.Connection):
    cursor_calls: int
    closed_cursors: int

    def cursor(self, factory: type[sqlite3.Cursor] = RecordingCursor) -> sqlite3.Cursor:
        self.cursor_calls += 1
        return super().cursor(factory=factory)


def test_prepared_statement_cache_reuses_cursor_for_same_sql() -> None:
    conn = sqlite3.connect(":memory:", factory=RecordingConnection)
    conn = cast(RecordingConnection, conn)
    conn.cursor_calls = 0
    conn.closed_cursors = 0
    cache = PreparedStatementCache(conn, maxsize=4)

    assert cache.fetchone("SELECT 1") == (1,)
    assert cache.fetchone("SELECT 1") == (1,)

    assert conn.cursor_calls == 1
    cache.close()
    conn.close()


def test_prepared_statement_cache_evicts_least_recently_used_cursor() -> None:
    conn = sqlite3.connect(":memory:", factory=RecordingConnection)
    conn = cast(RecordingConnection, conn)
    conn.cursor_calls = 0
    conn.closed_cursors = 0
    cache = PreparedStatementCache(conn, maxsize=2)

    assert cache.fetchone("SELECT 1") == (1,)
    assert cache.fetchone("SELECT 2") == (2,)
    assert cache.fetchone("SELECT 3") == (3,)

    assert len(cache) == 2
    assert conn.closed_cursors == 1
    cache.close()
    conn.close()


def test_statement_cache_for_reuses_connection_local_cache() -> None:
    conn = sqlite3.connect(":memory:")

    first = statement_cache_for(conn)
    second = statement_cache_for(conn)

    assert first is second
    clear_statement_cache(conn)
    third = statement_cache_for(conn)
    assert third is not first
    clear_statement_cache(conn)
    conn.close()
