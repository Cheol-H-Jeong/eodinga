from __future__ import annotations

from eodinga.query.dsl import AndNode, AstNode, NotNode, OperatorNode, OrNode, PhraseNode, QuerySyntaxError, RegexNode, parse


def _format_operator_value(node: OperatorNode) -> str:
    if node.value_kind == "phrase":
        escaped = node.value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if node.value_kind == "regex":
        return f"/{node.value}/{node.regex_flags}"
    return node.value


def _format_operator(node: OperatorNode, *, negated: bool) -> str:
    prefix = "-" if negated else ""
    return f"{prefix}{node.name}:{_format_operator_value(node)}"


def _collect_operator_filters(node: AstNode, *, negated: bool = False) -> list[str]:
    if isinstance(node, OperatorNode):
        return [_format_operator(node, negated=negated or node.negated)]
    if isinstance(node, NotNode):
        return _collect_operator_filters(node.clause, negated=not negated)
    if isinstance(node, (AndNode, OrNode)):
        filters: list[str] = []
        for child in node.clauses:
            filters.extend(_collect_operator_filters(child, negated=negated))
        return filters
    if isinstance(node, (PhraseNode, RegexNode)):
        return []
    return []


def collect_active_filters(query: str) -> tuple[str, ...]:
    if not query.strip():
        return ()
    try:
        ast = parse(query)
    except QuerySyntaxError:
        return ()
    filters = _collect_operator_filters(ast)
    deduped: list[str] = []
    for value in filters:
        if value not in deduped:
            deduped.append(value)
    return tuple(deduped)


__all__ = ["collect_active_filters"]
