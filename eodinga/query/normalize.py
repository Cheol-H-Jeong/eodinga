from __future__ import annotations

from eodinga.query.dsl import (
    AndNode,
    AstNode,
    NotNode,
    OperatorNode,
    OrNode,
    PhraseNode,
    RegexNode,
    WordNode,
)

_CANONICAL_DATE_KEYWORDS = {
    "today": "today",
    "yesterday": "yesterday",
    "tomorrow": "tomorrow",
    "week": "this-week",
    "this-week": "this-week",
    "last-week": "last-week",
    "prev-week": "last-week",
    "previous-week": "last-week",
    "month": "this-month",
    "this-month": "this-month",
    "last-month": "last-month",
    "prev-month": "last-month",
    "previous-month": "last-month",
    "year": "this-year",
    "this-year": "this-year",
    "last-year": "last-year",
    "prev-year": "last-year",
    "previous-year": "last-year",
}

_CANONICAL_IS_VALUES = {
    "dir": "dir",
    "directory": "dir",
    "folder": "dir",
    "file": "file",
    "symlink": "symlink",
    "link": "symlink",
    "empty": "empty",
    "duplicate": "duplicate",
    "dup": "duplicate",
}

_BOOLEAN_TRUE_VALUES = {"1", "true", "yes", "on"}
_BOOLEAN_FALSE_VALUES = {"0", "false", "no", "off"}
_REGEX_FLAG_ORDER = "ims"


def canonicalize_regex_flags(flags: str) -> str:
    ordered: list[str] = []
    seen: set[str] = set()
    for candidate in _REGEX_FLAG_ORDER:
        if candidate in flags.lower() and candidate not in seen:
            ordered.append(candidate)
            seen.add(candidate)
    return "".join(ordered)


def canonicalize_date_value(value: str) -> str:
    if ".." not in value:
        return _canonicalize_date_keyword(value)
    left, right = value.split("..", 1)
    return f"{_canonicalize_date_keyword(left)}..{_canonicalize_date_keyword(right)}"


def canonicalize_is_value(value: str) -> str:
    normalized = value.strip().casefold().replace("_", "-")
    return _CANONICAL_IS_VALUES.get(normalized, value.strip())


def canonicalize_bool_value(value: str) -> str:
    normalized = value.strip().casefold()
    if normalized in _BOOLEAN_TRUE_VALUES:
        return "true"
    if normalized in _BOOLEAN_FALSE_VALUES:
        return "false"
    return value.strip()


def canonicalize_operator(node: OperatorNode) -> OperatorNode:
    value = node.value
    regex_flags = node.regex_flags
    if node.name in {"date", "modified", "created"} and node.value_kind == "word":
        value = canonicalize_date_value(value)
    elif node.name == "is" and node.value_kind == "word":
        value = canonicalize_is_value(value)
    elif node.name in {"case", "regex"} and node.value_kind == "word":
        value = canonicalize_bool_value(value)
    if node.value_kind == "regex":
        regex_flags = canonicalize_regex_flags(regex_flags)
    return node.model_copy(update={"value": value, "regex_flags": regex_flags})


def canonicalize_ast(node: AstNode) -> AstNode:
    if isinstance(node, OperatorNode):
        return canonicalize_operator(node)
    if isinstance(node, RegexNode):
        return node.model_copy(update={"flags": canonicalize_regex_flags(node.flags)})
    if isinstance(node, (WordNode, PhraseNode)):
        return node
    if isinstance(node, NotNode):
        return NotNode(clause=canonicalize_ast(node.clause))
    if isinstance(node, AndNode):
        return AndNode(clauses=tuple(canonicalize_ast(clause) for clause in node.clauses))
    if isinstance(node, OrNode):
        return OrNode(clauses=tuple(canonicalize_ast(clause) for clause in node.clauses))
    raise TypeError(f"unsupported node: {type(node)!r}")


def render_query(node: AstNode) -> str:
    if isinstance(node, WordNode):
        return _with_negation(node.value, node.negated)
    if isinstance(node, PhraseNode):
        return _with_negation(_render_phrase(node.value), node.negated)
    if isinstance(node, RegexNode):
        return _with_negation(_render_regex(node.pattern, node.flags), node.negated)
    if isinstance(node, OperatorNode):
        return _with_negation(f"{node.name}:{_render_operator_value(node)}", node.negated)
    if isinstance(node, NotNode):
        rendered = render_query(node.clause)
        if isinstance(node.clause, (WordNode, PhraseNode, RegexNode, OperatorNode)):
            return f"-{rendered}"
        return f"-({rendered})"
    if isinstance(node, AndNode):
        return " ".join(_render_and_clause(clause) for clause in node.clauses)
    if isinstance(node, OrNode):
        return " | ".join(_render_or_clause(clause) for clause in node.clauses)
    raise TypeError(f"unsupported node: {type(node)!r}")


def _canonicalize_date_keyword(value: str) -> str:
    stripped = value.strip()
    normalized = stripped.casefold().replace("_", "-")
    return _CANONICAL_DATE_KEYWORDS.get(normalized, stripped)


def _render_phrase(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _render_regex(pattern: str, flags: str) -> str:
    return f"/{pattern}/{flags}"


def _render_operator_value(node: OperatorNode) -> str:
    if node.value_kind == "phrase":
        return _render_phrase(node.value)
    if node.value_kind == "regex":
        return _render_regex(node.value, node.regex_flags)
    return node.value


def _with_negation(value: str, negated: bool) -> str:
    return f"-{value}" if negated else value


def _render_and_clause(node: AstNode) -> str:
    rendered = render_query(node)
    if isinstance(node, OrNode):
        return f"({rendered})"
    return rendered


def _render_or_clause(node: AstNode) -> str:
    rendered = render_query(node)
    if isinstance(node, (AndNode, OrNode)):
        return f"({rendered})"
    return rendered


__all__ = [
    "canonicalize_ast",
    "canonicalize_bool_value",
    "canonicalize_date_value",
    "canonicalize_is_value",
    "canonicalize_operator",
    "canonicalize_regex_flags",
    "render_query",
]
