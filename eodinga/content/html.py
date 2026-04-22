from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

from eodinga.content.base import ParsedContent, ParserSpec, make_parsed_content
from eodinga.content.text import _decode_bytes
from eodinga.core.fs import read_bytes

HTML_EXTENSIONS = frozenset({"html", "htm", "xml", "svg"})

try:
    from selectolax.parser import HTMLParser as SelectolaxHTMLParser
except ImportError:  # pragma: no cover - optional dependency
    SelectolaxHTMLParser = None


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.title: str = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        cleaned = data.strip()
        if not cleaned:
            return
        if self._in_title and not self.title:
            self.title = cleaned
        self.parts.append(cleaned)


def _extract_with_selectolax(raw_text: str) -> tuple[str, str]:
    if SelectolaxHTMLParser is None:
        raise RuntimeError("selectolax is not available")
    parser = SelectolaxHTMLParser(raw_text)
    title = ""
    title_node = parser.css_first("title")
    if title_node is not None:
        title = title_node.text(strip=True)
    body_text = (
        parser.body.text(separator="\n", strip=True)
        if parser.body
        else parser.text(separator="\n")
    )
    return title, body_text


def _extract_with_stdlib(raw_text: str) -> tuple[str, str]:
    parser = _TextExtractor()
    parser.feed(raw_text)
    return parser.title, "\n".join(parser.parts)


def extract_html_text(raw_text: str) -> tuple[str, str]:
    if SelectolaxHTMLParser is not None:
        return _extract_with_selectolax(raw_text)
    return _extract_with_stdlib(raw_text)


def parse_html(path: Path, max_body_chars: int) -> ParsedContent:
    raw_text = _decode_bytes(read_bytes(path))
    title, body_text = extract_html_text(raw_text)
    head_text = "\n".join(body_text.splitlines()[:5]).strip()
    return make_parsed_content(
        title=title or path.stem,
        head_text=head_text,
        body_text=body_text,
        max_body_chars=max_body_chars,
    )


def get_parser_spec() -> ParserSpec:
    return ParserSpec(name="html", extensions=HTML_EXTENSIONS, parse=parse_html)
