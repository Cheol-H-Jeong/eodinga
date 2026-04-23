from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget

from eodinga.gui.design import FONT_11, SPACE_4, SPACE_8
from eodinga.query.dsl import AndNode, AstNode, NotNode, OperatorNode, OrNode, PhraseNode, RegexNode, WordNode, parse


def _term_text(node: OperatorNode | PhraseNode | RegexNode | WordNode) -> str:
    if isinstance(node, OperatorNode):
        value = node.value
        if node.value_kind == "phrase":
            value = f'"{value}"'
        elif node.value_kind == "regex":
            suffix = node.regex_flags
            value = f"/{value}/{suffix}"
        text = f"{node.name}:{value}"
    elif isinstance(node, PhraseNode):
        text = f'"{node.value}"'
    elif isinstance(node, RegexNode):
        text = f"/{node.pattern}/{node.flags}"
    else:
        text = node.value
    return f"-{text}" if node.negated else text


def _walk_terms(node: AstNode) -> list[OperatorNode | PhraseNode | RegexNode | WordNode]:
    if isinstance(node, (OperatorNode, PhraseNode, RegexNode, WordNode)):
        return [node]
    if isinstance(node, NotNode):
        return []
    if isinstance(node, (AndNode, OrNode)):
        terms: list[OperatorNode | PhraseNode | RegexNode | WordNode] = []
        for clause in node.clauses:
            terms.extend(_walk_terms(clause))
        return terms
    return []


def active_filter_chips(query: str) -> list[str]:
    normalized = query.strip()
    if not normalized:
        return []
    try:
        terms = _walk_terms(parse(normalized))
    except ValueError:
        return []
    chips: list[str] = []
    seen: set[str] = set()
    for term in terms:
        if not isinstance(term, OperatorNode):
            continue
        chip = _term_text(term)
        if chip in seen:
            continue
        seen.add(chip)
        chips.append(chip)
    return chips


class QueryChipButton(QPushButton):
    def __init__(self, text: str, *, accessible_name: str, parent=None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(accessible_name)
        self.setProperty("chip", True)
        self.setFixedHeight(28)
        self.setStyleSheet(
            f"QPushButton {{ min-height: 28px; padding: 0 {SPACE_8}px; font-size: {FONT_11}px; }}"
        )


class QueryChipRow(QWidget):
    chip_activated = Signal(str)

    def __init__(self, label: str, *, accessible_name: str, parent=None) -> None:
        super().__init__(parent)
        self.setAccessibleName(accessible_name)
        self._label_prefix = label
        self._buttons: list[QPushButton] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_4)

        self.label = QLabel(label, self)
        self.label.setProperty("role", "secondary")
        self.label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.label)

        self._chip_container = QHBoxLayout()
        self._chip_container.setContentsMargins(0, 0, 0, 0)
        self._chip_container.setSpacing(SPACE_4)
        layout.addLayout(self._chip_container)
        layout.addStretch(1)
        self.setVisible(False)

    def set_chips(self, chips: list[str], *, accessible_name_factory: Callable[[str], str]) -> None:
        while self._buttons:
            button = self._buttons.pop()
            self._chip_container.removeWidget(button)
            button.setParent(None)
            button.deleteLater()
        for chip in chips:
            button = QueryChipButton(chip, accessible_name=accessible_name_factory(chip), parent=self)
            button.clicked.connect(lambda checked=False, value=chip: self.chip_activated.emit(value))
            self._chip_container.addWidget(button)
            self._buttons.append(button)
        self.setVisible(bool(chips))
        self.label.setVisible(bool(chips))


__all__ = ["QueryChipRow", "active_filter_chips"]
