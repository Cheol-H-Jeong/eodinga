from __future__ import annotations

from eodinga.gui.launcher_filters import active_filter_chips


def test_active_filter_chips_returns_only_operator_terms() -> None:
    assert active_filter_chips('budget ext:pdf date:this-week -"draft" content:"release notes"') == [
        "ext:pdf",
        "date:this-week",
        'content:"release notes"',
    ]


def test_active_filter_chips_preserves_negated_and_regex_filters() -> None:
    assert active_filter_chips(r'-path:"Quarterly Review" content:/release\s+notes/i report') == [
        '-path:"Quarterly Review"',
        r"content:/release\s+notes/i",
    ]


def test_active_filter_chips_ignores_invalid_queries() -> None:
    assert active_filter_chips('content:"unterminated') == []
