from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re
from sqlite3 import Connection

from eodinga.query.compiler import CompiledQuery, compile_query
from eodinga.query.dsl import QuerySyntaxError, parse
from eodinga.query.executor import QueryResult, execute

_RELATIVE_DATE_QUERY_RE = re.compile(
    r"(?ix)"
    r"\b(?:date|modified|created)\s*:\s*"
    r"(?:"
    r"today|yesterday|tomorrow|"
    r"(?:this[-_]?)?week|last[-_]?week|prev(?:ious)?[-_]?week|"
    r"(?:this[-_]?)?month|last[-_]?month|prev(?:ious)?[-_]?month|"
    r"(?:this[-_]?)?year|last[-_]?year|prev(?:ious)?[-_]?year"
    r")\b"
)


@lru_cache(maxsize=128)
def _compile_cached(query: str) -> CompiledQuery:
    return compile_query(parse(query))


def compile(query: str) -> CompiledQuery:
    if _RELATIVE_DATE_QUERY_RE.search(query):
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
