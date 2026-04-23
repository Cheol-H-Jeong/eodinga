from __future__ import annotations

from collections.abc import Iterable
from html import escape
import re

from eodinga.query.dsl import AndNode, AstNode, NotNode, OperatorNode, OrNode, QuerySyntaxError, parse

_FILTER_BADGE_STYLE = (
    "display:inline-block; margin:0 6px 6px 0; padding:2px 8px; border-radius:999px; "
    "font-size:11px; font-weight:600; color:#0F766E; background:#CCFBF1;"
)


def format_empty_state_body(recent_queries: list[str], *, query: str) -> str:
    if not query:
        recent = ", ".join(recent_queries[:3]) if recent_queries else "No recent queries yet."
        return (
            f"Recent: {recent} Press Alt+Up to recall recent queries, Alt+1 through Alt+9 to open a top hit, "
            "Tab to move to results, Enter to open the top hit, and Ctrl+Enter to reveal its folder."
        )
    return (
        "Try another term or refine with filters like ext:pdf, date:this-week, and size:>10M. "
        "Press Tab to jump back to the filter or Esc to hide the launcher."
    )


def format_shortcut_hint(*, has_results: bool, has_query: bool, results_focused: bool) -> str:
    if not has_results:
        if has_query:
            return "Refine with ext:, date:, size:, or content: filters. Alt+Up recalls recent queries."
        return "Type a filename, path, or content term. Alt+Up recalls recent queries."
    if results_focused:
        return (
            "Enter opens. Alt+1..9 quick-picks. Up/Down wraps. "
            "Home/End and PgUp/PgDn jump. Ctrl+Enter reveals. Ctrl+A or Ctrl+L returns to filter."
        )
    return (
        "Tab moves to results. Down/Up navigate. Home/End and PgUp/PgDn jump. "
        "Enter opens the top hit. Alt+1..9 quick-picks. Alt+Up recalls recent queries."
    )


def format_filter_chip_markup(query: str) -> str:
    chips = list(_collect_filter_chips(query))
    if not chips:
        return ""
    rendered = "".join(f"<span style='{_FILTER_BADGE_STYLE}'>{escape(chip)}</span>" for chip in chips)
    return f"Filters: {rendered}"


def _collect_filter_chips(query: str) -> Iterable[str]:
    normalized = query.strip()
    if not normalized:
        return ()
    try:
        return _collect_operator_tokens(parse(normalized))
    except QuerySyntaxError:
        return _fallback_filter_tokens(normalized)


def _collect_operator_tokens(node: AstNode, *, negated: bool = False) -> tuple[str, ...]:
    if isinstance(node, OperatorNode):
        value = _format_operator_value(node)
        prefix = "-" if node.negated or negated else ""
        return (f"{prefix}{node.name}:{value}",)
    if isinstance(node, NotNode):
        return _collect_operator_tokens(node.clause, negated=not negated)
    if isinstance(node, (AndNode, OrNode)):
        chips: list[str] = []
        for clause in node.clauses:
            chips.extend(_collect_operator_tokens(clause, negated=negated))
        return tuple(dict.fromkeys(chips))
    return ()


def _format_operator_value(node: OperatorNode) -> str:
    if node.value_kind == "phrase":
        return f'"{node.value}"'
    if node.value_kind == "regex":
        return f"/{node.value}/{node.regex_flags}"
    return node.value


def _fallback_filter_tokens(query: str) -> tuple[str, ...]:
    matches = re.findall(r"(?<!\\S)-?[a-z]+:(?:\"[^\"]*\"|/[^/]+/[a-z]*|\\S+)", query)
    return tuple(dict.fromkeys(matches))
