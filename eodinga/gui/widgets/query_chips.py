from __future__ import annotations

import re

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from eodinga.gui.design import SPACE_8
from eodinga.query.dsl import AndNode, AstNode, NotNode, OperatorNode, OrNode, QuerySyntaxError, parse

_FALLBACK_OPERATOR_PATTERN = re.compile(
    r'(?:(?<=\s)|^)(-?(?:date|ext|path|size|modified|created|is|content|case|regex):(?:"[^"]*"|/\S+/\w*|\S+))'
)


def _format_operator_chip(node: OperatorNode) -> str:
    prefix = "-" if node.negated else ""
    value = node.value
    if node.value_kind == "phrase":
        value = f'"{value}"'
    if node.value_kind == "regex":
        suffix = node.regex_flags or ""
        value = f"/{value}/{suffix}"
    return f"{prefix}{node.name}:{value}"


def _collect_operator_chips(node: AstNode, *, negated: bool = False) -> list[str]:
    if isinstance(node, OperatorNode):
        chip = _format_operator_chip(node.model_copy(update={"negated": node.negated or negated}))
        return [chip]
    if isinstance(node, NotNode):
        return _collect_operator_chips(node.clause, negated=not negated)
    if isinstance(node, (AndNode, OrNode)):
        chips: list[str] = []
        for clause in node.clauses:
            chips.extend(_collect_operator_chips(clause, negated=negated))
        return chips
    return []


def extract_filter_chips(query: str) -> list[str]:
    normalized = query.strip()
    if not normalized:
        return []
    try:
        return _collect_operator_chips(parse(normalized))
    except QuerySyntaxError:
        return [match.group(1) for match in _FALLBACK_OPERATOR_PATTERN.finditer(normalized)]


class QueryChipBar(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Launcher query chips")
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(SPACE_8)
        self._layout.addStretch(1)
        self._labels: list[QLabel] = []
        self.setVisible(False)

    def set_chips(self, chips: list[str]) -> None:
        for label in self._labels:
            self._layout.removeWidget(label)
            label.deleteLater()
        self._labels.clear()
        for chip in chips:
            label = QLabel(chip, self)
            label.setProperty("chip", "true")
            self._layout.insertWidget(self._layout.count() - 1, label)
            self._labels.append(label)
        self.setVisible(bool(chips))

