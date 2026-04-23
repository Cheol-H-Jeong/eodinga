from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from eodinga.gui.design import SPACE_8


@dataclass(frozen=True)
class ChipAction:
    text: str
    query: str
    kind: str = "filter"


class ChipRow(QWidget):
    chip_clicked = Signal(str)

    def __init__(self, accessible_name: str, parent=None) -> None:
        super().__init__(parent)
        self.setAccessibleName(accessible_name)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(SPACE_8)
        self._layout.addStretch(1)
        self._buttons: list[QPushButton] = []
        self.setVisible(False)

    @property
    def buttons(self) -> list[QPushButton]:
        return list(self._buttons)

    def set_chips(self, chips: list[ChipAction]) -> None:
        for button in self._buttons:
            self._layout.removeWidget(button)
            button.deleteLater()
        self._buttons = []
        for chip in chips:
            button = QPushButton(chip.text, self)
            button.setProperty("chip", True)
            button.setProperty("chipKind", chip.kind)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.setAccessibleName(f"{chip.kind.title()} chip {chip.text}")
            button.clicked.connect(lambda _checked=False, query=chip.query: self.chip_clicked.emit(query))
            self._layout.insertWidget(self._layout.count() - 1, button)
            self._buttons.append(button)
        self.setVisible(bool(self._buttons))
