from __future__ import annotations

from eodinga.content.code import parse_code
from eodinga.content.registry import parse


def test_code_parser_happy_path(parser_fixtures_dir) -> None:
    parsed = parse_code(parser_fixtures_dir / "sample.py", max_body_chars=120)
    assert parsed.title == "Parser fixture module."
    assert "Parser fixture module." in parsed.head_text
    assert "def add" in parsed.body_text


def test_code_parser_malformed_fixture_returns_empty(parser_fixtures_dir) -> None:
    parsed = parse(parser_fixtures_dir / "malformed_code.py", max_body_chars=120)
    assert parsed.title == "malformed_code"
    assert parsed.head_text == ""
    assert parsed.body_text == ""
    assert parsed.content_sha == b""

