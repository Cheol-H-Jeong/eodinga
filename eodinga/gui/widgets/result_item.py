from __future__ import annotations

from html import escape
import re

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

from eodinga.common import SearchHit

HTML_MARGIN = 8


def highlight_text(text: str, query: str) -> str:
    if not query:
        return escape(text)
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    if pattern.search(text) is None:
        return escape(text)
    parts: list[str] = []
    cursor = 0
    for match in pattern.finditer(text):
        start, end = match.span()
        parts.append(escape(text[cursor:start]))
        parts.append(f"<mark>{escape(text[start:end])}</mark>")
        cursor = end
    parts.append(escape(text[cursor:]))
    return "".join(parts)


def format_hit_html(hit: SearchHit, query: str) -> str:
    primary = hit.highlighted_name or highlight_text(hit.name, query)
    secondary = hit.highlighted_path or highlight_text(str(hit.path), query)
    return (
        f"<div style='font-size:15px; font-weight:600'>{primary}</div>"
        f"<div style='font-size:11px; color:#6B7280'>{secondary}</div>"
    )


class ResultItemDelegate(QStyledItemDelegate):
    def paint(self, painter, option: QStyleOptionViewItem, index) -> None:
        doc = QTextDocument()
        html = index.data(Qt.ItemDataRole.DisplayRole) or ""
        doc.setHtml(html)

        style = option.widget.style() if option.widget is not None else None
        if style is not None:
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, option, painter, option.widget)

        painter.save()
        painter.translate(option.rect.left() + HTML_MARGIN, option.rect.top() + HTML_MARGIN)
        clip = QRect(0, 0, option.rect.width() - (HTML_MARGIN * 2), option.rect.height() - (HTML_MARGIN * 2))
        doc.drawContents(painter, clip)
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        doc = QTextDocument()
        doc.setHtml(index.data(Qt.ItemDataRole.DisplayRole) or "")
        return QSize(option.rect.width(), int(doc.size().height()) + (HTML_MARGIN * 2))
