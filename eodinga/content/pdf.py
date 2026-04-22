from __future__ import annotations

from io import BytesIO
from pathlib import Path

from pdfminer.high_level import extract_text as pdfminer_extract_text
from pypdf import PdfReader

from eodinga.content.base import ParsedContent, ParserSpec, make_parsed_content
from eodinga.core.fs import read_bytes


def _extract_with_pypdf(raw: bytes) -> str:
    reader = PdfReader(BytesIO(raw))
    return "\n".join(page.extract_text() or "" for page in reader.pages).strip()


def _extract_with_pdfminer(raw: bytes) -> str:
    return pdfminer_extract_text(BytesIO(raw)).strip()


def parse_pdf(path: Path, max_body_chars: int) -> ParsedContent:
    raw = read_bytes(path)
    body_text = _extract_with_pypdf(raw)
    if not body_text:
        body_text = _extract_with_pdfminer(raw)
    head_text = "\n".join(body_text.splitlines()[:5]).strip()
    title = head_text.splitlines()[0][:200] if head_text else path.stem
    return make_parsed_content(
        title=title,
        head_text=head_text,
        body_text=body_text,
        max_body_chars=max_body_chars,
    )


def get_parser_spec() -> ParserSpec:
    return ParserSpec(name="pdf", extensions=frozenset({"pdf"}), parse=parse_pdf)
