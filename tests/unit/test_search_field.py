from __future__ import annotations

from eodinga.gui.widgets.search_field import SearchField, extract_filter_chips


def test_extract_filter_chips_collects_unique_supported_filters() -> None:
    chips = extract_filter_chips('release ext:pdf size:>10M path:"Quarterly Reports" ext:pdf -is:dir')

    assert chips == ["ext:pdf", "size:>10M", 'path:"Quarterly Reports"', "-is:dir"]


def test_search_field_surfaces_filter_chips_in_overlay(qapp) -> None:
    field = SearchField()
    field.resize(640, 48)
    field.show()

    field.setText('budget ext:xlsx date:this-month content:"Q2 forecast"')

    assert field.filter_chips() == ["ext:xlsx", "date:this-month", 'content:"Q2 forecast"']
    assert field.textMargins().right() > 0


def test_search_field_hides_overlay_when_query_has_no_filters(qapp) -> None:
    field = SearchField()
    field.resize(640, 48)
    field.show()

    field.setText("notes")

    assert field.filter_chips() == []
    assert field.textMargins().right() == 0
