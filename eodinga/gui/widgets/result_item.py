from __future__ import annotations

from html import escape

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

from eodinga.common import SearchHit

HTML_MARGIN = 8


def highlight_text(text: str, query: str) -> str:
    if not query:
        return escape(text)
    lowered = text.lower()
    target = query.lower()
    start = lowered.find(target)
    if start < 0:
        return escape(text)
    end = start + len(target)
    return f"{escape(text[:start])}<mark>{escape(text[start:end])}</mark>{escape(text[end:])}"


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
