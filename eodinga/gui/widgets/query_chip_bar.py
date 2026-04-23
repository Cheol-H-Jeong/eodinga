from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from eodinga.gui.design import SPACE_4, SPACE_8

DEFAULT_CHIPS = ("ext:pdf", "date:this-week", "size:>10M", "content:invoice")


class QueryChipBar(QWidget):
    chip_selected = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Launcher query suggestions")
        self._buttons: list[QPushButton] = []
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(SPACE_4)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

    def set_chips(self, chips: Iterable[str]) -> None:
        labels: list[str] = []
        for chip in chips:
            normalized = chip.strip()
            if normalized and normalized not in labels:
                labels.append(normalized)
        while self._buttons:
            button = self._buttons.pop()
            self._layout.removeWidget(button)
            button.deleteLater()
        for chip in labels[:6]:
            button = QPushButton(chip, self)
            button.setProperty("variant", "secondary")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
            button.setAccessibleName(f"Launcher suggestion {chip}")
            button.setStyleSheet(f"padding: {SPACE_4}px {SPACE_8}px;")
            button.clicked.connect(lambda _checked=False, value=chip: self.chip_selected.emit(value))
            self._layout.addWidget(button)
            self._buttons.append(button)
        self.setVisible(bool(self._buttons))

    def chip_labels(self) -> list[str]:
        return [button.text() for button in self._buttons]


def suggested_chips(query: str, pinned_queries: list[str], recent_queries: list[str]) -> list[str]:
    query_text = query.strip().casefold()
    chips: list[str] = []
    for chip in pinned_queries:
        normalized = chip.strip()
        if normalized and normalized.casefold() not in query_text and normalized not in chips:
            chips.append(normalized)
    for chip in recent_queries:
        normalized = chip.strip()
        if normalized and normalized.casefold() not in query_text and normalized not in chips:
            chips.append(normalized)
    for chip in DEFAULT_CHIPS:
        if chip.casefold() not in query_text and chip not in chips:
            chips.append(chip)
    return chips[:6]
