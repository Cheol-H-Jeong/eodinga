from __future__ import annotations

from dataclasses import dataclass
import re

from eodinga.query.dsl import AndNode, AstNode, NotNode, OperatorNode, OrNode, QuerySyntaxError, parse

_FALLBACK_CHIP_RE = re.compile(
    r'(?P<token>-?(?:date|ext|path|size|modified|created|is|content|case|regex):(?:"[^"]*"|/\S+?/[A-Za-z]*|\S+))'
)


@dataclass(frozen=True)
class QueryChip:
    text: str
    query: str
    kind: str = "filter"


def collect_query_chips(query: str) -> list[QueryChip]:
    normalized = query.strip()
    if not normalized:
        return []
    try:
        ast = parse(normalized)
    except QuerySyntaxError:
        return _fallback_query_chips(normalized)
    chips: list[QueryChip] = []
    _append_query_chips(ast, chips, negated=False)
    return _dedupe_chips(chips)


def _append_query_chips(node: AstNode, chips: list[QueryChip], *, negated: bool) -> None:
    if isinstance(node, OperatorNode):
        value = _format_operator_value(node)
        prefix = "-" if negated or node.negated else ""
        token = f"{prefix}{node.name}:{value}"
        chips.append(QueryChip(text=token, query=token))
        return
    if isinstance(node, NotNode):
        _append_query_chips(node.clause, chips, negated=not negated)
        return
    if isinstance(node, (AndNode, OrNode)):
        for clause in node.clauses:
            _append_query_chips(clause, chips, negated=negated)


def _format_operator_value(node: OperatorNode) -> str:
    if node.value_kind == "phrase":
        escaped = node.value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if node.value_kind == "regex":
        return f"/{node.value}/{node.regex_flags}"
    return node.value


def _fallback_query_chips(query: str) -> list[QueryChip]:
    return _dedupe_chips([QueryChip(text=match.group("token"), query=match.group("token")) for match in _FALLBACK_CHIP_RE.finditer(query)])


def _dedupe_chips(chips: list[QueryChip]) -> list[QueryChip]:
    deduped: list[QueryChip] = []
    seen: set[str] = set()
    for chip in chips:
        if chip.text in seen:
            continue
        seen.add(chip.text)
        deduped.append(chip)
    return deduped
