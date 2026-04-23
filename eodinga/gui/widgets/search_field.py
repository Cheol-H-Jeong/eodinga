from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLineEdit

from eodinga.gui.design import FONT_18


class SearchField(QLineEdit):
    pin_requested = Signal()
    recall_previous_requested = Signal()
    recall_next_requested = Signal()

    def __init__(self, placeholder: str = "Search everything...", parent=None) -> None:
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        font = QFont(self.font())
        font.setPointSize(FONT_18)
        self.setFont(font)
        self.setClearButtonEnabled(True)

    def keyPressEvent(self, event) -> None:
        if event.modifiers() & Qt.KeyboardModifier.AltModifier:
            if event.key() == Qt.Key.Key_P:
                self.pin_requested.emit()
                event.accept()
                return
            if event.key() == Qt.Key.Key_Up:
                self.recall_previous_requested.emit()
                event.accept()
                return
            if event.key() == Qt.Key.Key_Down:
                self.recall_next_requested.emit()
                event.accept()
                return
        super().keyPressEvent(event)
