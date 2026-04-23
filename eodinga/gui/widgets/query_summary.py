from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from eodinga.gui.design import SPACE_4, SPACE_8
from eodinga.query.dsl import AndNode, AstNode, NotNode, OperatorNode, OrNode, PhraseNode, QuerySyntaxError, RegexNode, WordNode, parse


def _render_term(node: WordNode | PhraseNode | RegexNode | OperatorNode) -> str:
    if isinstance(node, WordNode):
        return node.value
    if isinstance(node, PhraseNode):
        return f'"{node.value}"'
    if isinstance(node, RegexNode):
        return f"/{node.pattern}/{node.flags}"
    if node.value_kind == "phrase":
        value = f'"{node.value}"'
    elif node.value_kind == "regex":
        value = f"/{node.value}/{node.regex_flags}"
    else:
        value = node.value
    return f"{node.name}:{value}"


def _collect_terms(node: AstNode, *, negated: bool = False) -> list[str]:
    effective_negated = negated
    if isinstance(node, (WordNode, PhraseNode, RegexNode, OperatorNode)):
        effective_negated = effective_negated or node.negated
        prefix = "NOT " if effective_negated else ""
        return [f"{prefix}{_render_term(node)}"]
    if isinstance(node, NotNode):
        return _collect_terms(node.clause, negated=not negated)
    if isinstance(node, (AndNode, OrNode)):
        labels: list[str] = []
        for child in node.clauses:
            labels.extend(_collect_terms(child, negated=negated))
        return labels
    return []


def summarize_query(query: str) -> tuple[list[str], str | None]:
    text = query.strip()
    if not text:
        return [], None
    try:
        labels = _collect_terms(parse(text))
    except QuerySyntaxError as exc:
        return [], f"Syntax: {exc.message}"
    deduped: list[str] = []
    for label in labels:
        if label not in deduped:
            deduped.append(label)
    return deduped, None


class QuerySummaryRow(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Active launcher query summary")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_8)

        self._label = QLabel("Active", self)
        self._label.setProperty("role", "secondary")
        self._chips_container = QWidget(self)
        self._chips_layout = QHBoxLayout(self._chips_container)
        self._chips_layout.setContentsMargins(0, 0, 0, 0)
        self._chips_layout.setSpacing(SPACE_4)

        layout.addWidget(self._label)
        layout.addWidget(self._chips_container, 1)
        layout.addStretch(1)

        self._chips: list[QLabel] = []
        self.setVisible(False)

    def set_query(self, query: str) -> None:
        labels, error = summarize_query(query)
        self._set_chips([error] if error else labels)

    def _set_chips(self, chips: list[str]) -> None:
        while self._chips:
            chip = self._chips.pop()
            self._chips_layout.removeWidget(chip)
            chip.deleteLater()
        for chip_text in chips[:6]:
            chip = QLabel(chip_text, self._chips_container)
            chip.setProperty("chip", True)
            chip.setTextFormat(Qt.TextFormat.PlainText)
            chip.setAccessibleName(f"Query summary {chip_text}")
            self._chips_layout.addWidget(chip)
            self._chips.append(chip)
        self.setVisible(bool(chips))

    @property
    def chips(self) -> list[QLabel]:
        return list(self._chips)
