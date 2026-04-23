from __future__ import annotations

from pathlib import Path

from eodinga.common import SearchHit
from eodinga.gui.widgets.result_item import format_hit_html, highlight_text


def test_highlight_text_renders_bold_mark_for_literal_match() -> None:
    rendered = highlight_text("release-notes.txt", "notes")

    assert "font-weight:700" in rendered
    assert ">notes</mark>" in rendered


def test_format_hit_html_applies_bold_mark_to_name_path_and_snippet() -> None:
    hit = SearchHit(
        path=Path("/tmp/release-notes.txt"),
        parent_path=Path("/tmp/releases"),
        name="release-notes.txt",
        snippet="Latest [release] summary",
        ext="txt",
    )

    rendered = format_hit_html(hit, "release")

    assert rendered.count("font-weight:700") >= 3
    assert "background:#FDE68A" in rendered
    assert "/tmp/<mark" in rendered
