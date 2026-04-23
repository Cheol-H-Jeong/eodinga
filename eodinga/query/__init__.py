from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from sqlite3 import Connection

from eodinga.query.compiler import CompiledQuery, compile_query
from eodinga.query.dsl import (
    AndNode,
    AstNode,
    NotNode,
    OperatorNode,
    OrNode,
    QuerySyntaxError,
    parse,
)
from eodinga.query.executor import QueryResult, execute


@lru_cache(maxsize=128)
def _compile_cached(query: str) -> CompiledQuery:
    return compile_query(parse(query))


def _uses_relative_dates(node: AstNode) -> bool:
    if isinstance(node, OperatorNode):
        if node.name not in {"date", "modified", "created"}:
            return False
        normalized = node.value.strip().casefold().replace("_", "-")
        return normalized in {
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
    if isinstance(node, (AndNode, OrNode)):
        return any(_uses_relative_dates(child) for child in node.clauses)
    if isinstance(node, NotNode):
        return _uses_relative_dates(node.clause)
    return False


def compile(query: str) -> CompiledQuery:
    ast = parse(query)
    if _uses_relative_dates(ast):
        return compile_query(ast)
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
