from __future__ import annotations

from html import escape
import re

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

from eodinga.common import SearchHit

HTML_MARGIN = 8


def _query_highlight_terms(query: str) -> tuple[str, ...]:
    terms: list[str] = []
    seen: set[str] = set()
    for raw in re.findall(r'"[^"]+"|\S+', query):
        token = raw.strip()
        if token in {"|", "-", ""}:
            continue
        is_negated = False
        while token.startswith("-"):
            is_negated = True
            token = token[1:].lstrip()
        normalized = token.strip("()")
        if is_negated or normalized == "":
            continue
        if normalized.startswith('"') and normalized.endswith('"') and len(normalized) > 1:
            normalized = normalized[1:-1]
        if ":" in normalized:
            continue
        folded = normalized.casefold()
        if folded in seen:
            continue
        seen.add(folded)
        terms.append(normalized)
    return tuple(terms)


def highlight_text(text: str, query: str) -> str:
    terms = sorted(_query_highlight_terms(query), key=len, reverse=True)
    if not terms:
        return escape(text)
    spans: list[tuple[int, int]] = []
    for term in terms:
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        spans.extend(match.span() for match in pattern.finditer(text))
    if not spans:
        return escape(text)
    spans.sort(key=lambda span: (span[0], -(span[1] - span[0])))
    parts: list[str] = []
    cursor = 0
    for start, end in spans:
        if start < cursor:
            continue
        parts.append(escape(text[cursor:start]))
        parts.append(f"<mark>{escape(text[start:end])}</mark>")
        cursor = end
    parts.append(escape(text[cursor:]))
    return "".join(parts)


def format_hit_html(hit: SearchHit, query: str) -> str:
    primary = hit.highlighted_name or highlight_text(hit.name, query)
    secondary = hit.highlighted_path or highlight_text(str(hit.path), query)
    ext_badge = ""
    if hit.ext:
        ext_badge = (
            "<span style='display:inline-block; margin-left:8px; padding:1px 6px; "
            "border-radius:999px; font-size:10px; font-weight:700; letter-spacing:0.08em; "
            "text-transform:uppercase; color:#92400E; background:#FEF3C7'>"
            f"{escape(hit.ext)}"
            "</span>"
        )
    return (
        f"<div style='font-size:15px; font-weight:600'>{primary}{ext_badge}</div>"
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
