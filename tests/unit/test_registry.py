from __future__ import annotations

from eodinga.content.registry import get_spec_for, load_specs, parse


def test_registry_dispatches_by_extension(parser_fixtures_dir) -> None:
    load_specs.cache_clear()
    assert get_spec_for(parser_fixtures_dir / "sample.txt") is not None
    assert get_spec_for(parser_fixtures_dir / "sample.pdf") is not None
    assert get_spec_for(parser_fixtures_dir / "sample.docx") is not None


def test_registry_unknown_extension_falls_back_to_filename_only(parser_fixtures_dir) -> None:
    path = parser_fixtures_dir / "unknown.bin"
    parsed = parse(path, max_body_chars=100)
    assert parsed.title == "unknown"
    assert parsed.head_text == ""
    assert parsed.body_text == ""
    assert parsed.content_sha == b""
