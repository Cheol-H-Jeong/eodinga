from __future__ import annotations

from eodinga.content.epub import parse_epub
from eodinga.content.registry import parse


def test_epub_parser_happy_path(parser_fixtures_dir) -> None:
    parsed = parse_epub(parser_fixtures_dir / "sample.epub", max_body_chars=240)
    assert parsed.title == "EPUB Fixture"
    assert "Chapter one body" in parsed.body_text


def test_epub_parser_malformed_fixture_returns_empty(parser_fixtures_dir) -> None:
    parsed = parse(parser_fixtures_dir / "malformed.epub", max_body_chars=240)
    assert parsed.title == "malformed"
    assert parsed.body_text == ""

