from __future__ import annotations

from eodinga.gui.launcher_query_summary import compact_filter_summary, summarize_active_filters


def test_summarize_active_filters_preserves_query_order_and_negation() -> None:
    filters = summarize_active_filters('report ext:pdf -is:dir date:this-week content:"release notes"')

    assert filters == ["ext:pdf", "-is:dir", "date:this-week", 'content:"release notes"']


def test_summarize_active_filters_formats_regex_values() -> None:
    filters = summarize_active_filters(r"path:/quarterly\/2026/i regex:true")

    assert filters == [r"path:/quarterly\/2026/i", "regex:true"]


def test_summarize_active_filters_hides_invalid_queries() -> None:
    assert summarize_active_filters('path:"unterminated') == []


def test_summarize_active_filters_can_return_full_filter_list() -> None:
    filters = summarize_active_filters("ext:pdf date:today size:>10M path:reports is:file regex:true", limit=None)

    assert filters == ["ext:pdf", "date:today", "size:>10M", "path:reports", "is:file", "regex:true"]


def test_compact_filter_summary_collapses_overflow() -> None:
    summary = compact_filter_summary("ext:pdf date:today size:>10M")

    assert summary == "ext:pdf  date:today  +1"


def test_compact_filter_summary_hides_plain_terms() -> None:
    assert compact_filter_summary("release notes") == ""
