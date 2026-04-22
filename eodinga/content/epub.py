from __future__ import annotations

from pathlib import Path

from ebooklib import ITEM_DOCUMENT, epub

from eodinga.content.base import ParsedContent, ParserSpec, make_parsed_content
from eodinga.content.html import extract_html_text
from eodinga.content.text import _decode_bytes


def parse_epub(path: Path, max_body_chars: int) -> ParsedContent:
    book = epub.read_epub(str(path))
    title_values = book.get_metadata("DC", "title")
    title = str(title_values[0][0]) if title_values else path.stem
    parts: list[str] = []
    for item in list(book.get_items_of_type(ITEM_DOCUMENT))[:5]:
        item_title, item_body = extract_html_text(_decode_bytes(item.get_content()))
        if item_title and title == path.stem:
            title = item_title
        if item_body:
            parts.append(item_body)
    body_text = "\n".join(parts)
    head_text = "\n".join(body_text.splitlines()[:5]).strip()
    return make_parsed_content(
        title=title,
        head_text=head_text,
        body_text=body_text,
        max_body_chars=max_body_chars,
    )


def get_parser_spec() -> ParserSpec:
    return ParserSpec(name="epub", extensions=frozenset({"epub"}), parse=parse_epub)
