from __future__ import annotations

from eodinga.query.dsl import AndNode, AstNode, NotNode, OperatorNode, OrNode, QuerySyntaxError, parse


def _format_filter(node: OperatorNode) -> str:
    value = node.value
    if node.value_kind == "phrase":
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        value = f'"{escaped}"'
    elif node.value_kind == "regex":
        value = f"/{value}/{node.regex_flags}"
    prefix = "-" if node.negated else ""
    return f"{prefix}{node.name}:{value}"


def _with_negation(node: OperatorNode) -> OperatorNode:
    return OperatorNode(
        name=node.name,
        value=node.value,
        value_kind=node.value_kind,
        regex_flags=node.regex_flags,
        negated=not node.negated,
    )


def _collect_filters(node: AstNode, *, negated: bool = False) -> list[str]:
    if isinstance(node, OperatorNode):
        return [_format_filter(_with_negation(node) if negated else node)]
    if isinstance(node, NotNode):
        return _collect_filters(node.clause, negated=not negated)
    if isinstance(node, (AndNode, OrNode)):
        filters: list[str] = []
        for child in node.clauses:
            filters.extend(_collect_filters(child, negated=negated))
        return filters
    return []


def summarize_active_filters(query: str, *, limit: int | None = 5) -> list[str]:
    normalized = query.strip()
    if not normalized:
        return []
    try:
        filters = _collect_filters(parse(normalized))
    except QuerySyntaxError:
        return []
    deduped: list[str] = []
    for item in filters:
        if item not in deduped:
            deduped.append(item)
        if limit is not None and len(deduped) >= limit:
            break
    return deduped


__all__ = ["summarize_active_filters"]
