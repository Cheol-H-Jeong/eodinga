from __future__ import annotations

from PySide6.QtCore import QTimer
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
        QTimer.singleShot(0, self._label_clear_button)

    def _label_clear_button(self) -> None:
        for button in self.findChildren(QToolButton):
            if button.accessibleName().strip():
                continue
            button.setAccessibleName("Clear launcher query")

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._label_clear_button()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._label_clear_button()
