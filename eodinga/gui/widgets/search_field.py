from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLineEdit

from eodinga.gui.design import FONT_18


class SearchField(QLineEdit):
    def __init__(self, placeholder: str = "Search everything...", parent=None) -> None:
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setToolTip("Type a query, then use Alt+Up for recent queries or Tab to reach launcher chips and results.")
        font = QFont(self.font())
        font.setPointSize(FONT_18)
        self.setFont(font)
        self.setClearButtonEnabled(True)
