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


def test_summarize_active_filters_preserves_negated_group_filters() -> None:
    filters = summarize_active_filters("-(ext:pdf | date:today) report")

    assert filters == ["-ext:pdf", "-date:today"]


def test_summarize_active_filters_flips_nested_negation_inside_groups() -> None:
    filters = summarize_active_filters("-(-ext:pdf | path:archive)")

    assert filters == ["ext:pdf", "-path:archive"]


def test_summarize_active_filters_can_return_full_filter_list() -> None:
    filters = summarize_active_filters("ext:pdf date:today size:>10M path:reports is:file regex:true", limit=None)

    assert filters == ["ext:pdf", "date:today", "size:>10M", "path:reports", "is:file", "regex:true"]


def test_summarize_active_filters_canonicalizes_alias_values() -> None:
    filters = summarize_active_filters("date:Previous_Month is:Folder regex:ON case:Yes")

    assert filters == ["date:last-month", "is:dir", "regex:true", "case:true"]


def test_summarize_active_filters_sorts_regex_flags_for_equivalent_filters() -> None:
    filters = summarize_active_filters(r"path:/quarterly\/2026/smi regex:/todo|fixme/mi")

    assert filters == [r"path:/quarterly\/2026/ims", r"regex:/todo|fixme/im"]
