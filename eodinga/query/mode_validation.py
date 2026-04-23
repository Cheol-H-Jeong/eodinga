from __future__ import annotations

from collections.abc import Callable

from eodinga.query.dsl import AndNode, AstNode, NotNode, OperatorNode, OrNode


def contains_group_mode_toggle(node: AstNode, parse_bool: Callable[[str], bool | None]) -> bool:
    if isinstance(node, OperatorNode):
        return (
            node.name in {"case", "regex"}
            and node.value_kind == "word"
            and parse_bool(node.value) is not None
        )
    if isinstance(node, (AndNode, OrNode)):
        return any(contains_group_mode_toggle(clause, parse_bool) for clause in node.clauses)
    if isinstance(node, NotNode):
        return contains_group_mode_toggle(node.clause, parse_bool)
    return False
