from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from eodinga.gui.design import SPACE_8
from eodinga.query.dsl import AndNode, AstNode, NotNode, OperatorNode, OrNode, QuerySyntaxError, parse


def _collect_filter_chips(node: AstNode, *, negated: bool = False) -> list[str]:
    if isinstance(node, OperatorNode):
        prefix = "-" if (negated or node.negated) else ""
        return [f"{prefix}{node.name}:{node.value}"]
    if isinstance(node, NotNode):
        return _collect_filter_chips(node.clause, negated=not negated)
    if isinstance(node, (AndNode, OrNode)):
        chips: list[str] = []
        for child in node.clauses:
            chips.extend(_collect_filter_chips(child, negated=negated))
        return chips
    return []


class FilterChipBar(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Launcher active filters")
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(SPACE_8)
        self._labels: list[QLabel] = []
        self.setVisible(False)

    @property
    def chip_texts(self) -> list[str]:
        return [label.text() for label in self._labels]

    def set_query(self, query: str) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        while self._labels:
            self._labels.pop()
        try:
            chips = _collect_filter_chips(parse(query))
        except QuerySyntaxError:
            chips = []
        for chip in dict.fromkeys(chips):
            label = QLabel(chip, self)
            label.setProperty("chip", True)
            label.setAccessibleName(f"Active filter {chip}")
            self._layout.addWidget(label)
            self._labels.append(label)
        self._layout.addStretch(1)
        self.setVisible(bool(self._labels))
