from __future__ import annotations

from eodinga.query.dsl import AndNode, AstNode, NotNode, OperatorNode, OrNode, QuerySyntaxError, parse


def active_filter_chips(query: str) -> list[str]:
    normalized = query.strip()
    if not normalized:
        return []
    try:
        return _collect_active_filters(parse(normalized))
    except QuerySyntaxError:
        return []


def _collect_active_filters(node: AstNode) -> list[str]:
    if isinstance(node, OperatorNode):
        return [_format_operator(node)]
    if isinstance(node, (AndNode, OrNode)):
        filters: list[str] = []
        for clause in node.clauses:
            filters.extend(_collect_active_filters(clause))
        return filters
    if isinstance(node, NotNode):
        return _collect_active_filters(node.clause)
    return []


def _format_operator(node: OperatorNode) -> str:
    prefix = "-" if node.negated else ""
    return f"{prefix}{node.name}:{_format_operator_value(node)}"


def _format_operator_value(node: OperatorNode) -> str:
    if node.value_kind == "phrase":
        escaped = node.value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if node.value_kind == "regex":
        return f"/{node.value}/{node.regex_flags}"
    return node.value
