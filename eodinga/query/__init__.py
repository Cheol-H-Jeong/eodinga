from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from sqlite3 import Connection

from eodinga.query.compiler import CompiledQuery, compile_query
from eodinga.query.dsl import QuerySyntaxError, parse
from eodinga.query.executor import QueryResult, execute


_DYNAMIC_DATE_FILTER_RE = re.compile(
    r"""
    \b(?:date|modified|created)\s*:\s*
    (?:
        (?:"[^"]*"|[^)\s|]+)
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)
_RELATIVE_DATE_KEYWORDS = {
    "today",
    "yesterday",
    "tomorrow",
    "week",
    "this-week",
    "last-week",
    "prev-week",
    "previous-week",
    "month",
    "this-month",
    "last-month",
    "prev-month",
    "previous-month",
    "year",
    "this-year",
    "last-year",
    "prev-year",
    "previous-year",
}


@lru_cache(maxsize=128)
def _compile_cached(query: str) -> CompiledQuery:
    return compile_query(parse(query))


def _has_dynamic_date_filter(query: str) -> bool:
    normalized = query.casefold().replace("_", "-")
    for match in _DYNAMIC_DATE_FILTER_RE.finditer(normalized):
        value = match.group(0).split(":", 1)[1].strip().strip('"')
        parts = [part.strip() for part in value.split("..", 1)]
        if any(part in _RELATIVE_DATE_KEYWORDS for part in parts if part):
            return True
    return False


def compile(query: str) -> CompiledQuery:
    if _has_dynamic_date_filter(query):
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
