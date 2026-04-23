from __future__ import annotations

from eodinga.gui.launcher_query_summary import summarize_active_filters


def test_summarize_active_filters_preserves_query_order_and_negation() -> None:
    filters = summarize_active_filters('report ext:pdf -is:dir date:this-week content:"release notes"')

    assert filters == ["ext:pdf", "-is:dir", "date:this-week", 'content:"release notes"']


def test_summarize_active_filters_formats_regex_values() -> None:
    filters = summarize_active_filters(r"path:/quarterly\/2026/i regex:true")

    assert filters == [r"path:/quarterly\/2026/i", "regex:true"]


def test_summarize_active_filters_hides_invalid_queries() -> None:
    assert summarize_active_filters('path:"unterminated') == []
