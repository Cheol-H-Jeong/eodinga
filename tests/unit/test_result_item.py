from __future__ import annotations

from pathlib import Path

from eodinga.common import SearchHit
from eodinga.gui.widgets.result_item import format_hit_html, highlight_text


def test_highlight_text_marks_all_case_insensitive_matches() -> None:
    rendered = highlight_text("Report report REPORT.txt", "report")

    assert rendered.count("<mark>") == 3
    assert "<mark><strong>Report</strong></mark>" in rendered
    assert "<mark><strong>report</strong></mark>" in rendered
    assert "<mark><strong>REPORT</strong></mark>" in rendered


def test_highlight_text_ignores_dsl_filters_and_marks_free_text_terms() -> None:
    rendered = highlight_text("release notes 2026.pdf", 'release ext:pdf date:this-week -"draft"')

    assert rendered.count("<mark>") == 1
    assert "<mark><strong>release</strong></mark>" in rendered
    assert "date:this-week" not in rendered


def test_highlight_text_marks_quoted_phrases() -> None:
    rendered = highlight_text("quarterly release notes.txt", '"release notes" ext:txt')

    assert "<mark><strong>release notes</strong></mark>" in rendered


def test_highlight_text_marks_escaped_quoted_phrases() -> None:
    rendered = highlight_text('release "candidate" notes.txt', r'"release \"candidate\""')

    assert "<mark><strong>release &quot;candidate&quot;</strong></mark>" in rendered


def test_highlight_text_ignores_negated_terms() -> None:
    rendered = highlight_text("draft release notes.txt", 'release -"draft"')

    assert "<mark><strong>release</strong></mark>" in rendered
    assert "<mark><strong>draft</strong></mark>" not in rendered


def test_highlight_text_supports_path_and_extension_filters_by_target() -> None:
    rendered_path = highlight_text("/tmp/reports/quarterly.pdf", "path:reports ext:pdf", target="path")
    rendered_ext = highlight_text("pdf", "path:reports ext:pdf", target="ext")

    assert "/tmp/<mark><strong>reports</strong></mark>/quarterly.pdf" in rendered_path
    assert "<mark><strong>pdf</strong></mark>" in rendered_ext


def test_highlight_text_supports_regex_and_content_filters() -> None:
    rendered_name = highlight_text("release-notes.txt", "/release[- ]notes/i", target="name")
    rendered_snippet = highlight_text("release notes are attached", 'content:"release notes"', target="snippet")

    assert "<mark><strong>release-notes</strong></mark>.txt" in rendered_name
    assert "<mark><strong>release notes</strong></mark>" in rendered_snippet


def test_highlight_text_respects_case_true_for_literals() -> None:
    rendered = highlight_text("Report report", "case:true Report", target="name")

    assert "<mark><strong>Report</strong></mark>" in rendered
    assert "<mark><strong>report</strong></mark>" not in rendered


def test_format_hit_html_renders_extension_badge() -> None:
    rendered = format_hit_html(
        SearchHit(
            path=Path("/tmp/report.pdf"),
            parent_path=Path("/tmp"),
            name="report.pdf",
            ext="pdf",
        ),
        "report",
        quick_pick_number=1,
    )

    assert "Alt+1" in rendered
    assert "<mark><strong>report</strong></mark>.pdf" in rendered
    assert ">pdf</span>" in rendered
    assert ">report.pdf</div><div" not in rendered
    assert ">/tmp</div>" in rendered


def test_format_hit_html_renders_highlighted_snippet() -> None:
    rendered = format_hit_html(
        SearchHit(
            path=Path("/tmp/release-notes.txt"),
            parent_path=Path("/tmp"),
            name="release-notes.txt",
            ext="txt",
            snippet="...the [release notes] are attached...",
        ),
        'content:"release notes"',
    )

    assert "<mark><strong>release notes</strong></mark>" in rendered
    assert "the " in rendered


def test_format_hit_html_shows_parent_path_line_for_path_filters() -> None:
    rendered = format_hit_html(
        SearchHit(
            path=Path("/workspace/reports/release-notes.txt"),
            parent_path=Path("/workspace/reports"),
            name="release-notes.txt",
            ext="txt",
        ),
        "path:reports",
    )

    assert "/workspace/<mark><strong>reports</strong></mark>" in rendered
    assert "release-notes.txt</div><div" not in rendered


def test_format_hit_html_prefers_precomputed_highlighted_path() -> None:
    rendered = format_hit_html(
        SearchHit(
            path=Path("/workspace/reports/release-notes.txt"),
            parent_path=Path("/workspace/reports"),
            name="release-notes.txt",
            ext="txt",
            highlighted_path="/workspace/<mark><strong>reports</strong></mark>",
        ),
        "path:ignored",
    )

    assert "/workspace/<mark><strong>reports</strong></mark>" in rendered
    assert "path:ignored" not in rendered


def test_format_hit_html_omits_quick_pick_badge_after_top_nine() -> None:
    rendered = format_hit_html(
        SearchHit(
            path=Path("/tmp/report.pdf"),
            parent_path=Path("/tmp"),
            name="report.pdf",
            ext="pdf",
        ),
        "report",
        quick_pick_number=None,
    )

    assert "Alt+" not in rendered
