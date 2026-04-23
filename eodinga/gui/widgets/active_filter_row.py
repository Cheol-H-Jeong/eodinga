from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from eodinga.gui.design import SPACE_8
from eodinga.gui.launcher_query_summary import summarize_active_filters

_CHIP_STYLE = (
    "display:inline-block; margin:0 6px 6px 0; padding:1px 8px; border-radius:999px; "
    "font-size:11px; font-weight:700; color:#0F766E; background:#CCFBF1"
)


class ActiveFilterRow(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Active launcher filters")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_8)

        self.title_label = QLabel("Filters", self)
        self.title_label.setProperty("role", "secondary")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.title_label.setAccessibleName("Active filter heading")
        self.chips_label = QLabel(self)
        self.chips_label.setWordWrap(True)
        self.chips_label.setTextFormat(Qt.TextFormat.RichText)
        self.chips_label.setAccessibleName("Active filter chips")
        self.chips_label.setAccessibleDescription("Visible query filters parsed from the launcher search.")
        layout.addWidget(self.title_label)
        layout.addWidget(self.chips_label, 1)
        self.set_query("")

    def set_query(self, query: str) -> None:
        filters = summarize_active_filters(query)
        self.setVisible(bool(filters))
        if not filters:
            self.chips_label.clear()
            return
        self.chips_label.setText("".join(f"<span style='{_CHIP_STYLE}'>{escape(item)}</span>" for item in filters))


__all__ = ["ActiveFilterRow"]
