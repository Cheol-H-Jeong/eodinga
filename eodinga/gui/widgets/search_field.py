from __future__ import annotations

import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QWidget

from eodinga.gui.design import FONT_18, SPACE_8

_FILTER_TOKEN = re.compile(r"(?<!\S)(-?(?:ext|path|content|date|modified|created|size|is|case|regex):(?:\"[^\"]*\"|\\.|[^\s])+)")


def extract_filter_chips(query: str) -> list[str]:
    seen: list[str] = []
    for match in _FILTER_TOKEN.finditer(query):
        token = match.group(1).strip()
        if token and token not in seen:
            seen.append(token)
    return seen


class SearchField(QLineEdit):
    def __init__(self, placeholder: str = "Search everything...", parent=None) -> None:
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        font = QFont(self.font())
        font.setPointSize(FONT_18)
        self.setFont(font)
        self.setClearButtonEnabled(True)
        self.setAccessibleDescription("Type free text and filters such as ext:pdf or date:this-week.")
        self._active_chips: list[str] = []

        self._chip_overlay = QWidget(self)
        self._chip_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._chip_overlay_layout = QHBoxLayout(self._chip_overlay)
        self._chip_overlay_layout.setContentsMargins(0, 0, 0, 0)
        self._chip_overlay_layout.setSpacing(4)
        self._chip_labels: list[QLabel] = []

        self.textChanged.connect(self._refresh_filter_chips)
        self._refresh_filter_chips(self.text())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._relayout_chips()

    def filter_chips(self) -> list[str]:
        return list(self._active_chips)

    def _refresh_filter_chips(self, query: str) -> None:
        chips = extract_filter_chips(query)
        self._active_chips = chips
        while len(self._chip_labels) < len(chips):
            label = QLabel(self._chip_overlay)
            label.setProperty("chip", "true")
            label.setProperty("role", "secondary")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setAccessibleName("Active launcher filter")
            self._chip_overlay_layout.addWidget(label)
            self._chip_labels.append(label)
        for index, label in enumerate(self._chip_labels):
            if index < len(chips):
                label.setText(chips[index])
                label.show()
            else:
                label.hide()
        self._relayout_chips()

    def _relayout_chips(self) -> None:
        active_labels = self._chip_labels[: len(self._active_chips)]
        if not active_labels:
            self._chip_overlay.hide()
            self.setTextMargins(0, 0, 0, 0)
            return
        self._chip_overlay.adjustSize()
        overlay_width = min(self._chip_overlay.sizeHint().width(), max(self.width() // 2, 120))
        overlay_height = self._chip_overlay.sizeHint().height()
        x = max(self.width() - overlay_width - SPACE_8, SPACE_8)
        y = max((self.height() - overlay_height) // 2, 0)
        self._chip_overlay.setGeometry(x, y, overlay_width, overlay_height)
        self._chip_overlay.show()
        self.setTextMargins(0, 0, overlay_width + (SPACE_8 * 2), 0)
