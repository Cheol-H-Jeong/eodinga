from __future__ import annotations

from pathlib import Path

from eodinga.common import SearchHit
from eodinga.gui.widgets.result_item import format_hit_accessible_text, format_hit_html, format_preview_html, highlight_text


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


def test_highlight_text_merges_overlapping_matches_into_one_span() -> None:
    rendered = highlight_text("abcde", "abc bcd")

    assert rendered == "<mark>abcd</mark>e"


def test_highlight_text_marks_escaped_quoted_phrases() -> None:
    rendered = highlight_text('release "candidate" notes.txt', r'"release \"candidate\""')

    assert "<mark>release &quot;candidate&quot;</mark>" in rendered


def test_highlight_text_ignores_negated_terms() -> None:
    rendered = highlight_text("draft release notes.txt", 'release -"draft"')

    assert "<mark>release</mark>" in rendered
    assert "<mark>draft</mark>" not in rendered


def test_highlight_text_supports_path_and_extension_filters_by_target() -> None:
    rendered_path = highlight_text("/tmp/reports/quarterly.pdf", "path:reports ext:pdf", target="path")
    rendered_ext = highlight_text("pdf", "path:reports ext:pdf", target="ext")

    assert "/tmp/<mark>reports</mark>/quarterly.pdf" in rendered_path
    assert "<mark>pdf</mark>" in rendered_ext


def test_highlight_text_supports_regex_and_content_filters() -> None:
    rendered_name = highlight_text("release-notes.txt", "/release[- ]notes/i", target="name")
    rendered_snippet = highlight_text("release notes are attached", 'content:"release notes"', target="snippet")

    assert "<mark>release-notes</mark>.txt" in rendered_name
    assert "<mark>release notes</mark>" in rendered_snippet


def test_highlight_text_respects_case_true_for_literals() -> None:
    rendered = highlight_text("Report report", "case:true Report", target="name")

    assert "<mark>Report</mark>" in rendered
    assert "<mark>report</mark>" not in rendered


def test_highlight_text_respects_negated_case_false_for_literals() -> None:
    rendered = highlight_text("Report report", "-case:false Report", target="name")

    assert "<mark>Report</mark>" in rendered
    assert "<mark>report</mark>" not in rendered


def test_highlight_text_uses_last_case_operator_override() -> None:
    rendered = highlight_text("Report report", "case:true case:false Report", target="name")

    assert "<mark>Report</mark>" in rendered
    assert "<mark>report</mark>" in rendered


def test_format_hit_html_renders_extension_badge() -> None:
    rendered = format_hit_html(
        SearchHit(
            path=Path("/tmp/report.pdf"),
            parent_path=Path("/tmp"),
            name="report.pdf",
            ext="pdf",
        ),
        "report",
        quick_pick_number=2,
    )

    assert "Alt+2" in rendered
    assert "font-weight:700" in rendered
    assert "background-color:#FDE68A" in rendered
    assert ">report</mark>.pdf" in rendered
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

    assert ">release notes</mark>" in rendered
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

    assert "/workspace/<mark style='font-weight:700; background-color:#FDE68A; color:#111827'>reports</mark>" in rendered
    assert "release-notes.txt</div><div" not in rendered


def test_format_hit_html_prefers_precomputed_highlighted_path() -> None:
    rendered = format_hit_html(
        SearchHit(
            path=Path("/workspace/reports/release-notes.txt"),
            parent_path=Path("/workspace/reports"),
            name="release-notes.txt",
            ext="txt",
            highlighted_path="/workspace/<mark>reports</mark>",
        ),
        "path:ignored",
    )

    assert "/workspace/<mark style='font-weight:700; background-color:#FDE68A; color:#111827'>reports</mark>" in rendered
    assert "path:ignored" not in rendered


def test_format_hit_html_omits_quick_pick_badge_after_top_nine() -> None:
    rendered = format_hit_html(
        SearchHit(
            path=Path("/workspace/reports/release-notes.txt"),
            parent_path=Path("/workspace/reports"),
            name="release-notes.txt",
            ext="txt",
        ),
        "release",
        quick_pick_number=10,
    )

    assert "Alt+10" not in rendered


def test_format_preview_html_highlights_path_and_snippet_matches() -> None:
    title, path_html, snippet_html = format_preview_html(
        SearchHit(
            path=Path("/workspace/reports/release-notes.txt"),
            parent_path=Path("/workspace/reports"),
            name="release-notes.txt",
            ext="txt",
            snippet="...the [release notes] are attached...",
        ),
        'path:reports content:"release notes"',
    )

    assert title == "release-notes.txt"
    assert "workspace/<mark style='font-weight:700; background-color:#FDE68A; color:#111827'>reports</mark>" in path_html
    assert ">release notes</mark>" in snippet_html


def test_format_hit_accessible_text_describes_quick_pick_path_and_snippet() -> None:
    rendered = format_hit_accessible_text(
        SearchHit(
            path=Path("/workspace/reports/release-notes.txt"),
            parent_path=Path("/workspace/reports"),
            name="release-notes.txt",
            ext="txt",
            snippet="...the [release notes] are attached...",
        ),
        "release",
        quick_pick_number=2,
    )

    assert "Quick pick Alt+2." in rendered
    assert "Name release-notes.txt." in rendered
    assert "Path /workspace/reports/release-notes.txt." in rendered
    assert "Extension txt." in rendered
    assert "Snippet ...the release notes are attached..." in rendered
