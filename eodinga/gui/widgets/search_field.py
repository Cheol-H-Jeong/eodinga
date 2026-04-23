from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QLineEdit

from eodinga.gui.design import FONT_18

_BASE_ACCESSIBLE_DESCRIPTION = "Type a filename, path, or content term to search the index."
_CHIP_STYLE = (
    "display:inline-block; margin-left:6px; padding:1px 8px; border-radius:999px; "
    "font-size:11px; font-weight:700; color:#0F766E; background:#CCFBF1"
)
_OVERFLOW_STYLE = (
    "display:inline-block; margin-left:6px; padding:1px 8px; border-radius:999px; "
    "font-size:11px; font-weight:700; color:#374151; background:#E5E7EB"
)


class SearchField(QLineEdit):
    def __init__(self, placeholder: str = "Search everything...", parent=None) -> None:
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setAccessibleDescription(_BASE_ACCESSIBLE_DESCRIPTION)
        font = QFont(self.font())
        font.setPointSize(FONT_18)
        self.setFont(font)
        self.setClearButtonEnabled(True)
        self._filter_summary: tuple[str, ...] = ()
        self._filter_summary_label = QLabel(self)
        self._filter_summary_label.setAccessibleName("Inline active filters")
        self._filter_summary_label.setAccessibleDescription(
            "Summarized active filters shown inside the launcher search field."
        )
        self._filter_summary_label.setTextFormat(Qt.TextFormat.RichText)
        self._filter_summary_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        self._filter_summary_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._filter_summary_label.setVisible(False)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_filter_summary_geometry()

    def set_filter_summary(self, filters: list[str]) -> None:
        self._filter_summary = tuple(filters)
        if not self._filter_summary:
            self._filter_summary_label.clear()
            self._filter_summary_label.setVisible(False)
            self._apply_accessible_description()
            self._update_filter_summary_geometry()
            return
        visible_filters = self._filter_summary[:2]
        html = "".join(f"<span style='{_CHIP_STYLE}'>{escape(item)}</span>" for item in visible_filters)
        hidden_count = len(self._filter_summary) - len(visible_filters)
        if hidden_count > 0:
            html += f"<span style='{_OVERFLOW_STYLE}'>+{hidden_count}</span>"
        self._filter_summary_label.setText(html)
        self._filter_summary_label.setVisible(True)
        self._apply_accessible_description()
        self._update_filter_summary_geometry()

    def _apply_accessible_description(self) -> None:
        if not self._filter_summary:
            self.setAccessibleDescription(_BASE_ACCESSIBLE_DESCRIPTION)
            self.setToolTip("")
            return
        filters = ", ".join(self._filter_summary)
        self.setAccessibleDescription(f"{_BASE_ACCESSIBLE_DESCRIPTION} Active filters: {filters}.")
        self.setToolTip(f"Active filters: {filters}")

    def _update_filter_summary_geometry(self) -> None:
        if not self._filter_summary_label.isVisible():
            self.setTextMargins(0, 0, 0, 0)
            return
        self._filter_summary_label.adjustSize()
        padding = 36
        available_width = max(self.contentsRect().width() // 2, 120)
        label_width = min(self._filter_summary_label.sizeHint().width(), available_width)
        height = self._filter_summary_label.sizeHint().height()
        rect = self.contentsRect()
        x = rect.right() - label_width - padding
        y = rect.y() + max((rect.height() - height) // 2, 0)
        self._filter_summary_label.setGeometry(x, y, label_width, height)
        self.setTextMargins(0, 0, label_width + padding, 0)
