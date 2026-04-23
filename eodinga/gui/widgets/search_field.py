from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLineEdit, QToolButton

from eodinga.gui.design import FONT_18


class SearchField(QLineEdit):
    def __init__(self, placeholder: str = "Search everything...", parent=None) -> None:
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        font = QFont(self.font())
        font.setPointSize(FONT_18)
        self.setFont(font)
        self.setClearButtonEnabled(True)
        for button in self.findChildren(QToolButton):
            button.setAccessibleName("Clear launcher search")
