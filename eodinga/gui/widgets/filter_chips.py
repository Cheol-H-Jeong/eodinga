from __future__ import annotations

from html import escape

from PySide6.QtWidgets import QLabel

from eodinga.query.dsl import AndNode, AstNode, NotNode, OperatorNode, OrNode, QuerySyntaxError, parse


def _format_chip(node: OperatorNode) -> str:
    if node.value_kind == "phrase":
        value = f'"{node.value}"'
    elif node.value_kind == "regex":
        value = f"/{node.value}/{node.regex_flags}"
    else:
        value = node.value
    prefix = "-" if node.negated else ""
    return f"{prefix}{node.name}:{value}"


def _collect_operator_chips(node: AstNode) -> list[str]:
    if isinstance(node, OperatorNode):
        return [_format_chip(node)]
    if isinstance(node, NotNode):
        return _collect_operator_chips(node.clause)
    if isinstance(node, (AndNode, OrNode)):
        chips: list[str] = []
        for clause in node.clauses:
            chips.extend(_collect_operator_chips(clause))
        return chips
    return []


def extract_filter_chips(query: str) -> tuple[str, ...]:
    if not query.strip():
        return ()
    try:
        chips = _collect_operator_chips(parse(query))
    except QuerySyntaxError:
        return ()
    deduped: list[str] = []
    seen: set[str] = set()
    for chip in chips:
        if chip in seen:
            continue
        seen.add(chip)
        deduped.append(chip)
    return tuple(deduped)


class FilterChipRow(QLabel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Launcher filter chips")
        self.setProperty("role", "secondary")
        self.setWordWrap(True)
        self.setVisible(False)

    def set_query(self, query: str) -> None:
        chips = extract_filter_chips(query)
        self.setVisible(bool(chips))
        if not chips:
            self.clear()
            return
        rendered = " ".join(
            (
                "<span style='display:inline-block; margin-right:6px; margin-bottom:4px; "
                "padding:2px 8px; border-radius:999px; background:#E5E7EB; color:#111827; "
                "font-size:11px; font-weight:600'>"
                f"{escape(chip)}"
                "</span>"
            )
            for chip in chips
        )
        self.setText(rendered)

