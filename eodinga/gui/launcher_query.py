from __future__ import annotations

from collections.abc import Iterable
import re

from eodinga.query.dsl import AndNode, AstNode, NotNode, OperatorNode, OrNode, QuerySyntaxError, parse

_FILTER_TOKEN_PATTERN = re.compile(
    r'(?<!\S)(-?(?:date|ext|path|size|modified|created|is|content|case|regex):(?:/[^/\s]*(?:\\.[^/\s]*)*/[A-Za-z]*|"[^"]*"|\S+))'
)


def extract_query_filter_chips(query: str) -> list[str]:
    normalized = query.strip()
    if not normalized:
        return []
    try:
        chips = list(_iter_filter_chips(parse(normalized)))
    except QuerySyntaxError:
        chips = _FILTER_TOKEN_PATTERN.findall(normalized)
    deduped: list[str] = []
    seen: set[str] = set()
    for chip in chips:
        if chip in seen:
            continue
        seen.add(chip)
        deduped.append(chip)
    return deduped


def _iter_filter_chips(node: AstNode, *, negated: bool = False) -> Iterable[str]:
    if isinstance(node, OperatorNode):
        prefix = "-" if negated or node.negated else ""
        yield f"{prefix}{_format_operator(node)}"
        return
    if isinstance(node, NotNode):
        yield from _iter_filter_chips(node.clause, negated=not negated)
        return
    if isinstance(node, (AndNode, OrNode)):
        for clause in node.clauses:
            yield from _iter_filter_chips(clause, negated=negated)


def _format_operator(node: OperatorNode) -> str:
    if node.value_kind == "phrase":
        escaped = node.value.replace("\\", "\\\\").replace('"', '\\"')
        return f'{node.name}:"{escaped}"'
    if node.value_kind == "regex":
        return f"{node.name}:/{node.value}/{node.regex_flags}"
    return f"{node.name}:{node.value}"


__all__ = ["extract_query_filter_chips"]
