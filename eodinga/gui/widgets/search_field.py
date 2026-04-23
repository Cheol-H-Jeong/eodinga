from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QLineEdit

from eodinga.gui.design import FONT_18


class SearchField(QLineEdit):
    def __init__(self, placeholder: str = "Search everything...", parent=None) -> None:
        super().__init__(parent)
        self._summary_margin = 12
        self._summary_width = 0
        self.setPlaceholderText(placeholder)
        self.setAccessibleDescription("Type a filename, path, or content term to search the index.")
        font = QFont(self.font())
        font.setPointSize(FONT_18)
        self.setFont(font)
        self.setClearButtonEnabled(True)

        self.summary_label = QLabel(self)
        self.summary_label.setProperty("role", "secondary")
        self.summary_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.summary_label.setAccessibleName("Launcher filter summary")
        self.summary_label.setAccessibleDescription("Compact summary of active launcher filters.")
        self.summary_label.hide()
        self._relayout_summary()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._relayout_summary()

    def set_filter_summary(self, summary: str) -> None:
        normalized = summary.strip()
        self.summary_label.setText(normalized)
        self.summary_label.setVisible(bool(normalized))
        self._summary_width = self.summary_label.sizeHint().width() if normalized else 0
        self._relayout_summary()

    def _relayout_summary(self) -> None:
        has_summary = self.summary_label.isVisible() and self._summary_width > 0
        right_margin = self._summary_width + self._summary_margin if has_summary else 0
        self.setTextMargins(0, 0, right_margin, 0)
        height = max(self.height() - 6, 0)
        self.summary_label.setGeometry(
            max(self.width() - self._summary_width - self._summary_margin, 0),
            3,
            self._summary_width,
            height,
        )
