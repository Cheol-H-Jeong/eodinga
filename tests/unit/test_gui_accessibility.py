from __future__ import annotations

from eodinga.gui.app import EodingaWindow
from eodinga.gui.launcher_window import LauncherWindow


def test_search_field_clear_button_is_named_for_screen_readers(qapp) -> None:
    launcher = LauncherWindow()
    launcher.show()
    qapp.processEvents()

    clear_button = launcher.query_field.clear_button()

    assert clear_button is not None
    assert clear_button.accessibleName() == "Clear launcher search"
    assert clear_button.accessibleDescription() == "Clear the current launcher query."


def test_app_labels_navigation_and_section_headings(qapp) -> None:
    window = EodingaWindow()
    window.show()

    assert window.tab_widget.tabBar().accessibleName() == "Main navigation tab bar"
    assert window.roots_tab.title_label.accessibleName() == "Roots tab title"
    assert window.roots_tab.body_label.accessibleName() == "Roots tab guidance"
    assert window.index_tab.title_label.accessibleName() == "Index tab title"
    assert window.index_tab.body_label.accessibleName() == "Index tab guidance"
    assert window.index_tab.progress_label.accessibleName() == "Indexing progress summary"
    assert window.settings_tab.title_label.accessibleName() == "Settings tab title"
    assert window.settings_tab.body_label.accessibleName() == "Settings tab guidance"
    assert window.about_tab.title_label.accessibleName() == "About tab title"
    assert window.about_tab.body_label.accessibleName() == "About tab summary"
    assert window.launcher_window.filter_suggestions_row.accessibleName() == "Launcher filter suggestions"
    assert window.launcher_window.filter_suggestions_row._label.accessibleName() == "Filters query label"
