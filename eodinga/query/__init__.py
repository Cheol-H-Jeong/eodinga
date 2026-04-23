from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from sqlite3 import Connection

from eodinga.query.compiler import CompiledQuery, compile_query
from eodinga.query.dsl import AndNode, NotNode, OperatorNode, OrNode, QuerySyntaxError, parse
from eodinga.query.executor import QueryResult, execute

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


def _value_has_dynamic_date_component(value: str) -> bool:
    parts = [part.strip().casefold().replace("_", "-") for part in value.split("..", 1)]
    return any(part in _RELATIVE_DATE_KEYWORDS for part in parts if part)


def _has_dynamic_date_filter(node) -> bool:
    if isinstance(node, OperatorNode):
        return node.name in {"date", "modified", "created"} and _value_has_dynamic_date_component(
            node.value
        )
    if isinstance(node, (AndNode, OrNode)):
        return any(_has_dynamic_date_filter(child) for child in node.clauses)
    if isinstance(node, NotNode):
        return _has_dynamic_date_filter(node.clause)
    return False


@lru_cache(maxsize=128)
def _compile_cached(query: str) -> CompiledQuery:
    return compile_query(parse(query))


def compile(query: str) -> CompiledQuery:
    parsed = parse(query)
    if _has_dynamic_date_filter(parsed):
        return compile_query(parsed)
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
