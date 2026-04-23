from __future__ import annotations

import sqlite3

from eodinga.query.sqlite_cache import PreparedStatementCache, clear_statement_cache, statement_cache_for


class RecordingCursor(sqlite3.Cursor):
    def close(self) -> None:
        self.connection.closed_cursors += 1  # type: ignore[attr-defined]
        super().close()


class RecordingConnection(sqlite3.Connection):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.cursor_calls = 0
        self.closed_cursors = 0

    def cursor(self, *args: object, **kwargs: object) -> sqlite3.Cursor:
        self.cursor_calls += 1
        kwargs.setdefault("factory", RecordingCursor)
        return super().cursor(*args, **kwargs)


def test_prepared_statement_cache_reuses_cursor_for_same_sql() -> None:
    conn = sqlite3.connect(":memory:", factory=RecordingConnection)
    cache = PreparedStatementCache(conn, maxsize=4)

    assert cache.fetchone("SELECT 1") == (1,)
    assert cache.fetchone("SELECT 1") == (1,)

    assert conn.cursor_calls == 1
    cache.close()
    conn.close()


def test_prepared_statement_cache_evicts_least_recently_used_cursor() -> None:
    conn = sqlite3.connect(":memory:", factory=RecordingConnection)
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
