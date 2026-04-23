from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from eodinga.gui.design import SPACE_8
from eodinga.gui.launcher_query_summary import summarize_active_filters

_CHIP_STYLE = (
    "display:inline-block; margin:0 6px 6px 0; padding:1px 8px; border-radius:999px; "
    "font-size:11px; font-weight:700; color:#0F766E; background:#CCFBF1"
)
_OVERFLOW_STYLE = (
    "display:inline-block; margin:0 6px 6px 0; padding:1px 8px; border-radius:999px; "
    "font-size:11px; font-weight:700; color:#374151; background:#E5E7EB"
)


class ActiveFilterRow(QWidget):
    filter_selected = Signal(str)
    _VISIBLE_FILTER_LIMIT = 5

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._link_targets: dict[str, str] = {}
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
        self.chips_label.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self.chips_label.setAccessibleName("Active filter chips")
        self.chips_label.setAccessibleDescription("Visible launcher filters. Click a chip to select that filter in the search field.")
        self.chips_label.linkActivated.connect(self._handle_link_activated)
        layout.addWidget(self.title_label)
        layout.addWidget(self.chips_label, 1)
        self.set_query("")

    def set_query(self, query: str) -> None:
        filters = summarize_active_filters(query, limit=None)
        self._link_targets = {}
        self.setVisible(bool(filters))
        if not filters:
            self.chips_label.clear()
            self.setAccessibleDescription("No active launcher filters.")
            return
        visible_filters = filters[: self._VISIBLE_FILTER_LIMIT]
        html_parts: list[str] = []
        for index, item in enumerate(visible_filters):
            link = f"filter-{index}"
            self._link_targets[link] = item
            html_parts.append(
                f"<a href='{link}' style='text-decoration:none; color:inherit'><span style='{_CHIP_STYLE}'>{escape(item)}</span></a>"
            )
        html = "".join(html_parts)
        hidden_count = len(filters) - len(visible_filters)
        if hidden_count > 0:
            html += f"<span style='{_OVERFLOW_STYLE}'>+{hidden_count} more</span>"
        self.chips_label.setText(html)
        self.setAccessibleDescription(
            f"Showing {len(visible_filters)} of {len(filters)} active launcher filters. Click a chip to select it in the search field."
        )

    def _handle_link_activated(self, link: str) -> None:
        filter_text = self._link_targets.get(link)
        if filter_text:
            self.filter_selected.emit(filter_text)


__all__ = ["ActiveFilterRow"]
