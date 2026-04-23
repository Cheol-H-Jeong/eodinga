from __future__ import annotations

from eodinga.query.dsl import AndNode, AstNode, NotNode, OperatorNode, OrNode, PhraseNode, QuerySyntaxError, RegexNode, WordNode, parse

_FILTER_OPERATOR_NAMES = frozenset({"date", "ext", "path", "size", "modified", "created", "is", "content", "case", "regex"})


def _quote_filter_value(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _format_filter_chip(node: OperatorNode) -> str:
    prefix = "-" if node.negated else ""
    if node.value_kind == "phrase":
        value = _quote_filter_value(node.value)
    elif node.value_kind == "regex":
        value = f"/{node.value}/{node.regex_flags}"
    else:
        value = node.value
    return f"{prefix}{node.name}:{value}"


def _collect_filter_chips(node: AstNode, *, negated: bool = False) -> list[str]:
    if isinstance(node, OperatorNode) and node.name in _FILTER_OPERATOR_NAMES:
        formatted = node.model_copy(update={"negated": negated or node.negated})
        return [_format_filter_chip(formatted)]
    if isinstance(node, NotNode):
        return _collect_filter_chips(node.clause, negated=not negated)
    if isinstance(node, (AndNode, OrNode)):
        chips: list[str] = []
        for clause in node.clauses:
            chips.extend(_collect_filter_chips(clause, negated=negated))
        return chips
    return []


def extract_active_filter_chips(query: str) -> list[str]:
    normalized = query.strip()
    if not normalized:
        return []
    try:
        ast = parse(normalized)
    except QuerySyntaxError:
        return []
    chips: list[str] = []
    for chip in _collect_filter_chips(ast):
        if chip not in chips:
            chips.append(chip)
    return chips


def _render_node(node: AstNode, *, precedence: int = 0) -> str:
    if isinstance(node, WordNode):
        rendered = f"-{node.value}" if node.negated else node.value
    elif isinstance(node, PhraseNode):
        rendered = _quote_filter_value(node.value)
        if node.negated:
            rendered = f"-{rendered}"
    elif isinstance(node, RegexNode):
        rendered = f"/{node.pattern}/{node.flags}"
        if node.negated:
            rendered = f"-{rendered}"
    elif isinstance(node, OperatorNode):
        rendered = _format_filter_chip(node)
    elif isinstance(node, NotNode):
        inner = _render_node(node.clause, precedence=1)
        rendered = f"-({inner})"
    elif isinstance(node, AndNode):
        rendered = " ".join(_render_node(clause, precedence=2) for clause in node.clauses)
    else:
        rendered = " | ".join(_render_node(clause, precedence=1) for clause in node.clauses)
    if isinstance(node, OrNode) and precedence > 1:
        return f"({rendered})"
    if isinstance(node, AndNode) and precedence > 2:
        return f"({rendered})"
    return rendered


def _drop_filter_chip(node: AstNode, target_chip: str, *, negated: bool = False) -> tuple[AstNode | None, bool]:
    if isinstance(node, OperatorNode):
        if node.name in _FILTER_OPERATOR_NAMES:
            formatted = _format_filter_chip(node.model_copy(update={"negated": negated or node.negated}))
            if formatted == target_chip:
                return None, True
        return node, False
    if isinstance(node, NotNode):
        clause, removed = _drop_filter_chip(node.clause, target_chip, negated=not negated)
        if clause is None:
            return None, removed
        if clause is node.clause:
            return node, removed
        return NotNode(clause=clause), removed
    if isinstance(node, (AndNode, OrNode)):
        clauses: list[AstNode] = []
        removed = False
        for clause in node.clauses:
            updated_clause, clause_removed = _drop_filter_chip(clause, target_chip, negated=negated)
            removed = removed or clause_removed
            if updated_clause is not None:
                clauses.append(updated_clause)
        if not clauses:
            return None, removed
        if len(clauses) == 1:
            return clauses[0], removed
        rebuilt = AndNode(clauses=tuple(clauses)) if isinstance(node, AndNode) else OrNode(clauses=tuple(clauses))
        return rebuilt, removed
    return node, False


def remove_active_filter_chip(query: str, chip: str) -> str:
    normalized = query.strip()
    if not normalized:
        return ""
    try:
        ast = parse(normalized)
    except QuerySyntaxError:
        return normalized.replace(chip, "", 1).strip()
    updated, removed = _drop_filter_chip(ast, chip)
    if not removed or updated is None:
        return "" if removed else normalized
    return _render_node(updated).strip()
