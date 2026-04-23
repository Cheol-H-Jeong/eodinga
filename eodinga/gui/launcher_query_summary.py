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


def _collect_filters(node: AstNode) -> list[str]:
    if isinstance(node, OperatorNode):
        return [_format_filter(node)]
    if isinstance(node, NotNode):
        return _collect_filters(node.clause)
    if isinstance(node, (AndNode, OrNode)):
        filters: list[str] = []
        for child in node.clauses:
            filters.extend(_collect_filters(child))
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


def compact_filter_summary(query: str, *, limit: int = 2) -> str:
    filters = summarize_active_filters(query, limit=None)
    if not filters:
        return ""
    visible_filters = filters[:limit]
    summary = "  ".join(visible_filters)
    hidden_count = len(filters) - len(visible_filters)
    if hidden_count > 0:
        summary = f"{summary}  +{hidden_count}"
    return summary


__all__ = ["compact_filter_summary", "summarize_active_filters"]
