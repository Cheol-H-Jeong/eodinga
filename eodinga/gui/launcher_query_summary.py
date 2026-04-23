from __future__ import annotations

from eodinga.query.dsl import AndNode, AstNode, NotNode, OperatorNode, OrNode, QuerySyntaxError, parse
from eodinga.query.normalize import canonicalize_operator


def _format_filter(node: OperatorNode, *, negated: bool = False) -> str:
    canonical = canonicalize_operator(node)
    value = canonical.value
    if canonical.value_kind == "phrase":
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        value = f'"{escaped}"'
    elif canonical.value_kind == "regex":
        value = f"/{value}/{canonical.regex_flags}"
    prefix = "-" if (canonical.negated ^ negated) else ""
    return f"{prefix}{canonical.name}:{value}"


def _collect_filters(node: AstNode, *, negated: bool = False) -> list[str]:
    if isinstance(node, OperatorNode):
        return [_format_filter(node, negated=negated)]
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
