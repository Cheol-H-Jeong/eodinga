from __future__ import annotations

from eodinga.content.pdf import parse_pdf
from eodinga.content.registry import parse


def test_pdf_parser_happy_path(parser_fixtures_dir) -> None:
    parsed = parse_pdf(parser_fixtures_dir / "sample.pdf", max_body_chars=200)
    assert parsed.title.startswith("PDF fixture line one")
    assert "PDF fixture line two" in parsed.body_text


def test_pdf_parser_malformed_fixture_returns_empty(parser_fixtures_dir) -> None:
    parsed = parse(parser_fixtures_dir / "malformed.pdf", max_body_chars=200)
    assert parsed.title == "malformed"
    assert parsed.body_text == ""
