from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import QLabel, QLineEdit
from PySide6.QtGui import QResizeEvent

from eodinga.gui.design import FONT_18
from eodinga.gui.query_chips import extract_query_chips, render_query_chips_html


class SearchField(QLineEdit):
    pin_toggle_requested = Signal()

    def __init__(self, placeholder: str = "Search everything...", parent=None) -> None:
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        font = QFont(self.font())
        font.setPointSize(FONT_18)
        self.setFont(font)
        self.setClearButtonEnabled(True)
        self._chip_label = QLabel(self)
        self._chip_label.setAccessibleName("Active query filters")
        self._chip_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._chip_label.setTextFormat(Qt.TextFormat.RichText)
        self._chip_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._chip_label.hide()
        self.textChanged.connect(self._refresh_inline_chips)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._position_chip_label()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_P and event.modifiers() == Qt.KeyboardModifier.AltModifier:
            self.pin_toggle_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def filter_chip_text(self) -> str:
        return self._chip_label.text()

    def _refresh_inline_chips(self, query: str) -> None:
        chips = extract_query_chips(query)
        if not chips:
            self._chip_label.hide()
            self._chip_label.clear()
            self.setTextMargins(0, 0, 0, 0)
            return
        self._chip_label.setText(render_query_chips_html(chips))
        self._chip_label.setToolTip(", ".join(chips))
        self._chip_label.setAccessibleDescription(f"Active filters: {', '.join(chips)}")
        self._chip_label.adjustSize()
        self._position_chip_label()
        self._chip_label.show()
        self.setTextMargins(0, 0, self._chip_label.width() + 12, 0)

    def _position_chip_label(self) -> None:
        if not self._chip_label.text():
            return
        margin = 8
        height = self.height() - (margin * 2)
        self._chip_label.move(max(self.width() - self._chip_label.width() - 28, margin), margin)
        self._chip_label.resize(self._chip_label.width(), max(height, self._chip_label.height()))
