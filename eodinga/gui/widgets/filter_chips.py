from __future__ import annotations

from html import escape
import re

from PySide6.QtWidgets import QLabel

from eodinga.query.dsl import AndNode, AstNode, NotNode, OperatorNode, OrNode, QuerySyntaxError, parse

_FALLBACK_OPERATOR_RE = re.compile(
    r'(?<!\S)(-)?((?:date|ext|path|size|modified|created|is|content|case|regex):(?:\"[^\"]*\"|/[^/\n]+/[A-Za-z]*|\S+))'
)


def _format_operator_value(node: OperatorNode) -> str:
    if node.value_kind == "phrase":
        return f'"{node.value}"'
    if node.value_kind == "regex":
        return f"/{node.value}/{node.regex_flags}"
    return node.value


def _collect_filter_tokens(node: AstNode, *, negated: bool = False) -> list[str]:
    if isinstance(node, OperatorNode):
        prefix = "-" if negated or node.negated else ""
        return [f"{prefix}{node.name}:{_format_operator_value(node)}"]
    if isinstance(node, NotNode):
        return _collect_filter_tokens(node.clause, negated=not negated)
    if isinstance(node, (AndNode, OrNode)):
        tokens: list[str] = []
        for clause in node.clauses:
            tokens.extend(_collect_filter_tokens(clause, negated=negated))
        return tokens
    return []


def extract_filter_tokens(query: str) -> tuple[str, ...]:
    normalized = query.strip()
    if not normalized:
        return ()
    try:
        ast = parse(normalized)
    except QuerySyntaxError:
        return tuple(match.group(1) + match.group(2) if match.group(1) else match.group(2) for match in _FALLBACK_OPERATOR_RE.finditer(normalized))
    seen: set[str] = set()
    ordered: list[str] = []
    for token in _collect_filter_tokens(ast):
        if token in seen:
            continue
        seen.add(token)
        ordered.append(token)
    return tuple(ordered)


def render_filter_chips_html(query: str) -> str:
    tokens = extract_filter_tokens(query)
    if not tokens:
        return ""
    chips = "".join(
        "<span style='display:inline-block; margin-right:6px; margin-bottom:4px; "
        "padding:2px 8px; border-radius:999px; font-size:11px; font-weight:700; "
        "color:#115E59; background:#CCFBF1'>"
        f"{escape(token)}"
        "</span>"
        for token in tokens
    )
    return f"<span style='color:#4B5563; font-size:11px;'>Active filters </span>{chips}"


class FilterChips(QLabel):
    def __init__(self, parent=None) -> None:
        super().__init__("", parent)
        self.setAccessibleName("Active query filters")
        self.setWordWrap(True)
        self.setTextFormat(self.textFormat().RichText)
        self.setVisible(False)

    def set_query(self, query: str) -> None:
        html = render_filter_chips_html(query)
        self.setText(html)
        self.setVisible(bool(html))
