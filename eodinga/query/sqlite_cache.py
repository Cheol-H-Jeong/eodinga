from __future__ import annotations

import sqlite3
from collections import OrderedDict
from collections.abc import Iterable, Sequence


class PreparedStatementCache:
    def __init__(self, conn: sqlite3.Connection, *, maxsize: int = 128) -> None:
        self._conn = conn
        self._maxsize = maxsize
        self._cursors: OrderedDict[str, sqlite3.Cursor] = OrderedDict()

    def fetchall(
        self,
        sql: str,
        params: Sequence[object] | Iterable[object] = (),
    ) -> list[sqlite3.Row]:
        cursor = self._cursor(sql)
        return cursor.execute(sql, tuple(params)).fetchall()

    def fetchone(
        self,
        sql: str,
        params: Sequence[object] | Iterable[object] = (),
    ) -> sqlite3.Row | tuple[object, ...] | None:
        cursor = self._cursor(sql)
        return cursor.execute(sql, tuple(params)).fetchone()

    def __len__(self) -> int:
        return len(self._cursors)

    def close(self) -> None:
        for cursor in self._cursors.values():
            cursor.close()
        self._cursors.clear()

    def _cursor(self, sql: str) -> sqlite3.Cursor:
        cursor = self._cursors.pop(sql, None)
        if cursor is None:
            cursor = self._conn.cursor()
        self._cursors[sql] = cursor
        self._evict_if_needed()
        return cursor

    def _evict_if_needed(self) -> None:
        while len(self._cursors) > self._maxsize:
            _, cursor = self._cursors.popitem(last=False)
            cursor.close()


_STATEMENT_CACHES: dict[int, PreparedStatementCache] = {}


def statement_cache_for(
    conn: sqlite3.Connection, *, maxsize: int = 128
) -> PreparedStatementCache:
    cache = _STATEMENT_CACHES.get(id(conn))
    if cache is None:
        cache = PreparedStatementCache(conn, maxsize=maxsize)
        _STATEMENT_CACHES[id(conn)] = cache
    return cache


def clear_statement_cache(conn: sqlite3.Connection) -> None:
    cache = _STATEMENT_CACHES.pop(id(conn), None)
    if cache is not None:
        cache.close()


__all__ = ["PreparedStatementCache", "clear_statement_cache", "statement_cache_for"]
