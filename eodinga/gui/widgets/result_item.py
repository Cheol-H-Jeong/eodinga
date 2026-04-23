from __future__ import annotations

from dataclasses import dataclass
from html import escape
import re

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

from eodinga.common import SearchHit
from eodinga.query.dsl import (
    AndNode,
    AstNode,
    NotNode,
    OperatorNode,
    OrNode,
    PhraseNode,
    QuerySyntaxError,
    RegexNode,
    WordNode,
    parse,
)

HTML_MARGIN = 8
MARK_OPEN = "<mark style='font-weight:700; background-color:#FDE68A; color:#111827'>"
_TARGET_ALL = frozenset({"name", "path", "snippet"})


@dataclass(frozen=True)
class _HighlightRule:
    pattern: str
    flags: int
    targets: frozenset[str]
    is_regex: bool = False


def _literal_rule(pattern: str, targets: frozenset[str], flags: int) -> _HighlightRule:
    return _HighlightRule(pattern=pattern, flags=flags, targets=targets)


def _regex_rule(pattern: str, targets: frozenset[str], flags: int) -> _HighlightRule:
    return _HighlightRule(pattern=pattern, flags=flags, targets=targets, is_regex=True)


def _regex_flags(flag_text: str, default_case_sensitive: bool) -> int:
    flags = 0
    for flag in flag_text.lower():
        if flag == "i":
            flags |= re.IGNORECASE
        if flag == "m":
            flags |= re.MULTILINE
        if flag == "s":
            flags |= re.DOTALL
    if "i" not in flag_text.lower() and not default_case_sensitive:
        flags |= re.IGNORECASE
    return flags


def _query_case_sensitive(node: AstNode) -> bool:
    if isinstance(node, OperatorNode) and node.name == "case" and not node.negated:
        return node.value.casefold() == "true"
    if isinstance(node, (AndNode, OrNode)):
        return any(_query_case_sensitive(child) for child in node.clauses)
    if isinstance(node, NotNode):
        return False
    return False


def _collect_highlight_rules(
    node: AstNode,
    *,
    default_case_sensitive: bool,
    negated: bool = False,
) -> list[_HighlightRule]:
    effective_negated = negated
    if isinstance(node, (WordNode, PhraseNode, RegexNode, OperatorNode)):
        effective_negated = effective_negated or node.negated
    if effective_negated:
        return []
    if isinstance(node, WordNode):
        flags = 0 if default_case_sensitive else re.IGNORECASE
        return [_literal_rule(node.value, _TARGET_ALL, flags)]
    if isinstance(node, PhraseNode):
        flags = 0 if default_case_sensitive else re.IGNORECASE
        return [_literal_rule(node.value, _TARGET_ALL, flags)]
    if isinstance(node, RegexNode):
        return [_regex_rule(node.pattern, _TARGET_ALL, _regex_flags(node.flags, default_case_sensitive))]
    if isinstance(node, OperatorNode):
        if node.name in {"date", "size", "modified", "created", "is", "case", "regex"}:
            return []
        targets = _TARGET_ALL
        if node.name == "ext":
            targets = frozenset({"ext"})
        if node.name == "path":
            targets = frozenset({"path"})
        if node.name == "content":
            targets = frozenset({"snippet"})
        flags = 0 if default_case_sensitive else re.IGNORECASE
        if node.value_kind == "regex":
            return [_regex_rule(node.value, targets, _regex_flags(node.regex_flags, default_case_sensitive))]
        return [_literal_rule(node.value, targets, flags)]
    if isinstance(node, NotNode):
        return _collect_highlight_rules(
            node.clause,
            default_case_sensitive=default_case_sensitive,
            negated=not negated,
        )
    if isinstance(node, (AndNode, OrNode)):
        rules: list[_HighlightRule] = []
        for child in node.clauses:
            rules.extend(
                _collect_highlight_rules(
                    child,
                    default_case_sensitive=default_case_sensitive,
                    negated=negated,
                )
            )
        return rules
    return []


def _fallback_rules(query: str) -> tuple[_HighlightRule, ...]:
    rules: list[_HighlightRule] = []
    seen: set[tuple[str, frozenset[str], bool, int]] = set()
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
        key = (normalized.casefold(), _TARGET_ALL, False, re.IGNORECASE)
        if key in seen:
            continue
        seen.add(key)
        rules.append(_literal_rule(normalized, _TARGET_ALL, re.IGNORECASE))
    return tuple(rules)


def _highlight_rules(query: str) -> tuple[_HighlightRule, ...]:
    if not query.strip():
        return ()
    try:
        ast = parse(query)
    except QuerySyntaxError:
        return _fallback_rules(query)
    default_case_sensitive = _query_case_sensitive(ast)
    rules = _collect_highlight_rules(ast, default_case_sensitive=default_case_sensitive)
    deduped: list[_HighlightRule] = []
    seen: set[tuple[str, frozenset[str], bool, int]] = set()
    for rule in rules:
        key = (rule.pattern, rule.targets, rule.is_regex, rule.flags)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(rule)
    return tuple(deduped)


def _spans_for_rule(text: str, rule: _HighlightRule) -> list[tuple[int, int]]:
    pattern = rule.pattern if rule.is_regex else re.escape(rule.pattern)
    try:
        compiled = re.compile(pattern, rule.flags)
    except re.error:
        return []
    spans = [match.span() for match in compiled.finditer(text)]
    return [span for span in spans if span[0] != span[1]]


def highlight_text(text: str, query: str, *, target: str = "name") -> str:
    rules = tuple(rule for rule in _highlight_rules(query) if target in rule.targets)
    if not rules:
        return escape(text)
    spans: list[tuple[int, int]] = []
    for rule in rules:
        spans.extend(_spans_for_rule(text, rule))
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


def _highlight_fts_snippet(snippet: str) -> str:
    parts: list[str] = []
    cursor = 0
    while True:
        start = snippet.find("[", cursor)
        if start < 0:
            parts.append(escape(snippet[cursor:]))
            break
        end = snippet.find("]", start + 1)
        if end < 0:
            parts.append(escape(snippet[cursor:]))
            break
        parts.append(escape(snippet[cursor:start]))
        parts.append(f"{MARK_OPEN}{escape(snippet[start + 1:end])}</mark>")
        cursor = end + 1
    return "".join(parts)


def _style_marks(html: str) -> str:
    return html.replace("<mark>", MARK_OPEN)


def _quick_pick_badge(rank: int | None) -> str:
    if rank is None or rank < 1 or rank > 9:
        return ""
    return (
        "<span style='display:inline-block; margin-right:8px; padding:1px 6px; "
        "border-radius:999px; font-size:10px; font-weight:700; letter-spacing:0.06em; "
        "text-transform:uppercase; color:#1D4ED8; background:#DBEAFE'>"
        f"Alt+{rank}"
        "</span>"
    )


def format_hit_html(hit: SearchHit, query: str, *, quick_pick_rank: int | None = None) -> str:
    primary = _style_marks(hit.highlighted_name or highlight_text(hit.name, query, target="name"))
    secondary = _style_marks(hit.highlighted_path or highlight_text(str(hit.parent_path), query, target="path"))
    snippet_html = ""
    if hit.snippet:
        rendered_snippet = (
            _highlight_fts_snippet(hit.snippet)
            if "[" in hit.snippet and "]" in hit.snippet
            else highlight_text(hit.snippet, query, target="snippet")
        )
        snippet_html = f"<div style='font-size:11px; color:#374151; margin-top:4px'>{_style_marks(rendered_snippet)}</div>"
    ext_badge = ""
    if hit.ext:
        ext_html = _style_marks(highlight_text(hit.ext, query, target="ext"))
        ext_badge = (
            "<span style='display:inline-block; margin-left:8px; padding:1px 6px; "
            "border-radius:999px; font-size:10px; font-weight:700; letter-spacing:0.08em; "
            "text-transform:uppercase; color:#92400E; background:#FEF3C7'>"
            f"{ext_html}"
            "</span>"
        )
    return (
        f"<div style='font-size:15px; font-weight:600'>{_quick_pick_badge(quick_pick_rank)}{primary}{ext_badge}</div>"
        f"<div style='font-size:11px; color:#6B7280'>{secondary}</div>"
        f"{snippet_html}"
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
