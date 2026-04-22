from __future__ import annotations

from eodinga.gui.widgets.result_item import highlight_text


def test_highlight_text_marks_all_case_insensitive_matches() -> None:
    rendered = highlight_text("Report report REPORT.txt", "report")

    assert rendered.count("<mark>") == 3
    assert "<mark>Report</mark>" in rendered
    assert "<mark>report</mark>" in rendered
    assert "<mark>REPORT</mark>" in rendered
