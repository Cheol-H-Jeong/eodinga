from __future__ import annotations

from eodinga.gui.app import EodingaWindow
from eodinga.gui.tabs import AboutTab, IndexTab, RootsTab, SearchTab, SettingsTab


def test_app_window_has_expected_tabs(qapp) -> None:
    window = EodingaWindow()
    window.show()

    assert window.tab_widget.count() == 5
    assert isinstance(window.roots_tab, RootsTab)
    assert isinstance(window.index_tab, IndexTab)
    assert isinstance(window.search_tab, SearchTab)
    assert isinstance(window.settings_tab, SettingsTab)
    assert isinstance(window.about_tab, AboutTab)

