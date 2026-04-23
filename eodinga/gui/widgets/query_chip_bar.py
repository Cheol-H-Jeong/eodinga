from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from eodinga.gui.design import SPACE_8


class QueryChipBar(QWidget):
    query_selected = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Launcher query suggestions")
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(SPACE_8)
        self._buttons: list[QPushButton] = []
        self.setVisible(False)

    @property
    def button_texts(self) -> list[str]:
        return [button.text() for button in self._buttons]

    @property
    def buttons(self) -> tuple[QPushButton, ...]:
        return tuple(self._buttons)

    def set_queries(self, *, pinned: Sequence[str], recent: Sequence[str]) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        while self._buttons:
            self._buttons.pop()
        added: set[str] = set()
        for kind, queries in (("Pinned", pinned), ("Recent", recent)):
            for query in queries:
                normalized = query.strip()
                if not normalized or normalized in added:
                    continue
                added.add(normalized)
                button = QPushButton(normalized, self)
                button.setProperty("chip", True)
                button.setAccessibleName(f"{kind} query {normalized}")
                button.clicked.connect(lambda _checked=False, value=normalized: self.query_selected.emit(value))
                self._layout.addWidget(button)
                self._buttons.append(button)
        self._layout.addStretch(1)
        self.setVisible(bool(self._buttons))
