from __future__ import annotations

from eodinga.content.office import parse_docx, parse_pptx, parse_xlsx
from eodinga.content.registry import parse


def test_docx_parser_happy_path(parser_fixtures_dir) -> None:
    parsed = parse_docx(parser_fixtures_dir / "sample.docx", max_body_chars=200)
    assert parsed.title == "DOCX fixture title"
    assert "Second paragraph" in parsed.body_text


def test_docx_parser_malformed_fixture_returns_empty(parser_fixtures_dir) -> None:
    parsed = parse(parser_fixtures_dir / "malformed.docx", max_body_chars=200)
    assert parsed.title == "malformed"
    assert parsed.body_text == ""


def test_pptx_parser_happy_path(parser_fixtures_dir) -> None:
    parsed = parse_pptx(parser_fixtures_dir / "sample.pptx", max_body_chars=200)
    assert parsed.title == "PPTX fixture title"
    assert "Slide body text" in parsed.body_text


def test_pptx_parser_malformed_fixture_returns_empty(parser_fixtures_dir) -> None:
    parsed = parse(parser_fixtures_dir / "malformed.pptx", max_body_chars=200)
    assert parsed.title == "malformed"
    assert parsed.body_text == ""


def test_xlsx_parser_happy_path(parser_fixtures_dir) -> None:
    parsed = parse_xlsx(parser_fixtures_dir / "sample.xlsx", max_body_chars=200)
    assert parsed.title == "[SheetOne]"
    assert "alpha | beta" in parsed.body_text


def test_xlsx_parser_malformed_fixture_returns_empty(parser_fixtures_dir) -> None:
    parsed = parse(parser_fixtures_dir / "malformed.xlsx", max_body_chars=200)
    assert parsed.title == "malformed"
    assert parsed.body_text == ""

