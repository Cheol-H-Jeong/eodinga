from __future__ import annotations

from eodinga.content.hwp import parse_hwp
from eodinga.content.registry import parse


def test_hwp_parser_happy_path_returns_filename_title(parser_fixtures_dir) -> None:
    parsed = parse_hwp(parser_fixtures_dir / "sample.hwp", max_body_chars=200)
    assert parsed.title == "sample"
    assert parsed.head_text == ""
    assert parsed.body_text == ""


def test_hwp_parser_malformed_fixture_returns_empty(parser_fixtures_dir, monkeypatch) -> None:
    monkeypatch.setattr(
        "eodinga.content.hwp.olefile.isOleFile",
        lambda _path: (_ for _ in ()).throw(OSError("boom")),
    )
    parsed = parse(parser_fixtures_dir / "malformed.hwp", max_body_chars=200)
    assert parsed.title == "malformed"
    assert parsed.body_text == ""
