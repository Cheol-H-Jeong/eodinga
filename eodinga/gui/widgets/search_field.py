from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLineEdit, QToolButton

from eodinga.gui.design import FONT_18


class SearchField(QLineEdit):
    def __init__(self, placeholder: str = "Search everything...", parent=None) -> None:
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setAccessibleDescription("Type a filename, path, or content term to search the index.")
        font = QFont(self.font())
        font.setPointSize(FONT_18)
        self.setFont(font)
        self.setClearButtonEnabled(True)
        self._label_clear_button()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._label_clear_button()

    def clear_button(self) -> QToolButton | None:
        buttons = self.findChildren(QToolButton)
        return buttons[0] if buttons else None

    def _label_clear_button(self) -> None:
        button = self.clear_button()
        if button is None:
            return
        button.setAccessibleName("Clear launcher search")
        button.setAccessibleDescription("Clear the current launcher query.")
