from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLineEdit

from eodinga.gui.design import FONT_18


class SearchField(QLineEdit):
    pin_query_requested = Signal()

    def __init__(self, placeholder: str = "Search everything...", parent=None) -> None:
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        font = QFont(self.font())
        font.setPointSize(FONT_18)
        self.setFont(font)
        self.setClearButtonEnabled(True)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_D and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.pin_query_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)
