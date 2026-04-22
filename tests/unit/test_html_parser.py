from __future__ import annotations

from eodinga.content.html import parse_html
from eodinga.content.registry import parse


def test_html_parser_happy_path(parser_fixtures_dir) -> None:
    parsed = parse_html(parser_fixtures_dir / "sample.html", max_body_chars=120)
    assert parsed.title == "Fixture HTML"
    assert "Hello parser" in parsed.body_text
    assert "Alpha beta" in parsed.head_text


def test_html_parser_malformed_fixture_returns_empty(parser_fixtures_dir, monkeypatch) -> None:
    monkeypatch.setattr(
        "eodinga.content.html.read_bytes",
        lambda _path: (_ for _ in ()).throw(OSError("boom")),
    )
    parsed = parse(parser_fixtures_dir / "malformed.html", max_body_chars=120)
    assert parsed.title == "malformed"
    assert parsed.body_text == ""
