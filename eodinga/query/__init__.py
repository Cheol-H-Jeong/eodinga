from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from sqlite3 import Connection

from eodinga.query.compiler import CompiledQuery, compile_query
from eodinga.query.date_range import RELATIVE_DATE_KEYWORDS
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

_RELATIVE_DATE_KEYWORDS = RELATIVE_DATE_KEYWORDS


def _is_relative_date_value(value: str) -> bool:
    for part in value.split("..", 1):
        normalized = part.strip().casefold()
        if normalized in _RELATIVE_DATE_KEYWORDS:
            return True
    return False


def _uses_relative_date(node: AstNode) -> bool:
    if isinstance(node, OperatorNode):
        return (
            node.name in {"date", "modified", "created"}
            and node.value_kind == "word"
            and _is_relative_date_value(node.value)
        )
    if isinstance(node, (AndNode, OrNode)):
        return any(_uses_relative_date(clause) for clause in node.clauses)
    if isinstance(node, NotNode):
        return _uses_relative_date(node.clause)
    return False


@lru_cache(maxsize=128)
def _compile_cached(query: str) -> CompiledQuery:
    return compile_query(parse(query))


def compile(query: str) -> CompiledQuery:
    parsed = parse(query)
    if _uses_relative_date(parsed):
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
