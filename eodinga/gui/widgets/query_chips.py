from __future__ import annotations

from dataclasses import dataclass
from html import escape
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from eodinga.query.dsl import AndNode, AstNode, NotNode, OperatorNode, OrNode, PhraseNode, QuerySyntaxError, RegexNode, WordNode, parse


@dataclass(frozen=True)
class QueryChip:
    label: str
    role: str = "term"


def _format_operator_value(node: OperatorNode) -> str:
    if node.value_kind == "phrase":
        return f'"{node.value}"'
    if node.value_kind == "regex":
        return f"/{node.value}/{node.regex_flags}"
    return node.value


def _collect_query_chips(node: AstNode, *, negated: bool = False) -> list[QueryChip]:
    effective_negated = negated
    if isinstance(node, (WordNode, PhraseNode, RegexNode, OperatorNode)):
        effective_negated = effective_negated or node.negated
    if effective_negated:
        return []
    if isinstance(node, WordNode):
        return [QueryChip(node.value)]
    if isinstance(node, PhraseNode):
        return [QueryChip(f'"{node.value}"')]
    if isinstance(node, RegexNode):
        return [QueryChip(f"/{node.pattern}/{node.flags}")]
    if isinstance(node, OperatorNode):
        return [QueryChip(f"{node.name}:{_format_operator_value(node)}", role="filter")]
    if isinstance(node, NotNode):
        return _collect_query_chips(node.clause, negated=True)
    if isinstance(node, (AndNode, OrNode)):
        chips: list[QueryChip] = []
        for child in node.clauses:
            chips.extend(_collect_query_chips(child, negated=negated))
        return chips
    return []


def _fallback_query_chips(query: str) -> tuple[QueryChip, ...]:
    chips: list[QueryChip] = []
    for raw in re.findall(r'"[^"]+"|/[^/]+/[a-zA-Z]*|\S+', query):
        token = raw.strip()
        if not token or token in {"|", "-", "()"}:
            continue
        while token.startswith("-"):
            token = token[1:].lstrip()
        if not token:
            continue
        role = "filter" if ":" in token else "term"
        chips.append(QueryChip(token, role=role))
    return _dedupe_chips(chips)


def _dedupe_chips(chips: list[QueryChip]) -> tuple[QueryChip, ...]:
    deduped: list[QueryChip] = []
    seen: set[tuple[str, str]] = set()
    for chip in chips:
        key = (chip.label, chip.role)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(chip)
    return tuple(deduped)


def summarize_query_chips(query: str) -> tuple[QueryChip, ...]:
    if not query.strip():
        return ()
    try:
        return _dedupe_chips(_collect_query_chips(parse(query)))
    except QuerySyntaxError:
        return _fallback_query_chips(query)


class QueryChipLabel(QLabel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Active query chips")
        self.setWordWrap(True)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.setVisible(False)

    def set_query(self, query: str) -> None:
        chips = summarize_query_chips(query)
        self.setVisible(bool(chips))
        if not chips:
            self.clear()
            self.setAccessibleDescription("")
            return
        self.setAccessibleDescription(", ".join(chip.label for chip in chips))
        self.setText(_render_query_chips(chips))


def _render_query_chips(chips: tuple[QueryChip, ...]) -> str:
    rendered = []
    for chip in chips:
        background = "#CCFBF1" if chip.role == "filter" else "#E5E7EB"
        foreground = "#115E59" if chip.role == "filter" else "#374151"
        rendered.append(
            "<span style='display:inline-block; margin:0 6px 6px 0; padding:3px 8px; "
            "border-radius:999px; font-size:11px; font-weight:600; "
            f"background:{background}; color:{foreground}'>"
            f"{escape(chip.label)}"
            "</span>"
        )
    return "".join(rendered)


__all__ = ["QueryChip", "QueryChipLabel", "summarize_query_chips"]
