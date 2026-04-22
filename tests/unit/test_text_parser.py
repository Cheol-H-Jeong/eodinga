from __future__ import annotations

from hashlib import blake2b

from eodinga.content.registry import parse
from eodinga.content.text import parse_text


def test_text_parser_happy_path(parser_fixtures_dir) -> None:
    path = parser_fixtures_dir / "sample.txt"
    parsed = parse_text(path, max_body_chars=32)
    assert parsed.title == "Sample text title"
    assert parsed.head_text.startswith("Sample text title")
    assert parsed.body_text == "Sample text title\nSecond line wi"
    assert parsed.content_sha == blake2b(parsed.body_text.encode("utf-8"), digest_size=16).digest()


def test_text_parser_malformed_fixture_returns_empty(parser_fixtures_dir, monkeypatch) -> None:
    monkeypatch.setattr(
        "eodinga.content.text.read_bytes",
        lambda _path: (_ for _ in ()).throw(OSError("boom")),
    )
    parsed = parse(parser_fixtures_dir / "malformed.txt", max_body_chars=100)
    assert parsed.title == "malformed"
    assert parsed.head_text == ""
    assert parsed.body_text == ""
    assert parsed.content_sha == b""
