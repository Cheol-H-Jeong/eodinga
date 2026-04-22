from __future__ import annotations

from pathlib import Path

from eodinga.common import SearchHit
from eodinga.gui.widgets.result_item import format_hit_html, highlight_text


def test_highlight_text_marks_all_case_insensitive_matches() -> None:
    rendered = highlight_text("Report report REPORT.txt", "report")

    assert rendered.count("<mark>") == 3
    assert "<mark>Report</mark>" in rendered
    assert "<mark>report</mark>" in rendered
    assert "<mark>REPORT</mark>" in rendered


def test_highlight_text_ignores_dsl_filters_and_marks_free_text_terms() -> None:
    rendered = highlight_text("release notes 2026.pdf", 'release ext:pdf date:this-week -"draft"')

    assert rendered.count("<mark>") == 1
    assert "<mark>release</mark>" in rendered
    assert "date:this-week" not in rendered


def test_highlight_text_marks_quoted_phrases() -> None:
    rendered = highlight_text("quarterly release notes.txt", '"release notes" ext:txt')

    assert "<mark>release notes</mark>" in rendered


def test_highlight_text_ignores_negated_terms() -> None:
    rendered = highlight_text("draft release notes.txt", 'release -"draft"')

    assert "<mark>release</mark>" in rendered
    assert "<mark>draft</mark>" not in rendered


def test_format_hit_html_renders_extension_badge() -> None:
    rendered = format_hit_html(
        SearchHit(
            path=Path("/tmp/report.pdf"),
            parent_path=Path("/tmp"),
            name="report.pdf",
            ext="pdf",
        ),
        "report",
    )

    assert "<mark>report</mark>.pdf" in rendered
    assert ">pdf</span>" in rendered
