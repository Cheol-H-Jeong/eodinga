from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re
from sqlite3 import Connection

from eodinga.query.compiler import CompiledQuery, compile_query
from eodinga.query.dsl import QuerySyntaxError, parse
from eodinga.query.executor import QueryResult, execute


@lru_cache(maxsize=128)
def _compile_cached(query: str) -> CompiledQuery:
    return compile_query(parse(query))


_RELATIVE_DATE_QUERY = re.compile(
    r"(?i)\b(?:date|modified|created):(?:today|yesterday|tomorrow|this[-_]week|week|last[-_]week|prev[-_]week|previous[-_]week|this[-_]month|month|last[-_]month|prev[-_]month|previous[-_]month|this[-_]year|year|last[-_]year|prev[-_]year|previous[-_]year)\b"
)


def compile(query: str) -> CompiledQuery:
    if _RELATIVE_DATE_QUERY.search(query):
        return compile_query(parse(query))
    return _compile_cached(query)


def search(
    conn: Connection, query_str: str, limit: int = 200, root: Path | None = None
) -> QueryResult:
    return execute(conn, compile(query_str), limit=limit, root=root)


__all__ = [
    "CompiledQuery",
    "QueryResult",
    "QuerySyntaxError",
    "compile",
    "execute",
    "parse",
    "search",
]
