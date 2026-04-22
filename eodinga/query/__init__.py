from __future__ import annotations

from sqlite3 import Connection

from eodinga.query.compiler import CompiledQuery, compile_query
from eodinga.query.dsl import QuerySyntaxError, parse
from eodinga.query.executor import QueryResult, execute


def compile(query: str) -> CompiledQuery:
    return compile_query(parse(query))


def search(conn: Connection, query_str: str, limit: int = 200) -> QueryResult:
    return execute(conn, compile(query_str), limit=limit)


__all__ = [
    "CompiledQuery",
    "QueryResult",
    "QuerySyntaxError",
    "compile",
    "execute",
    "parse",
    "search",
]
