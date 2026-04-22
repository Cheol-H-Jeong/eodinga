from __future__ import annotations

from pathlib import Path
from typing import cast

from eodinga.common import IndexingStatus, QueryResult, SearchHit
from eodinga.gui.app import EodingaWindow, launch_gui
from eodinga.gui.launcher import LauncherWindow
from eodinga.gui.tabs import AboutTab, IndexTab, RootsTab, SearchTab, SettingsTab


def test_app_window_has_expected_tabs_and_launcher(qapp) -> None:
    _, window, launcher = cast(tuple[object, EodingaWindow, LauncherWindow], launch_gui(test_mode=True))
    window.show()

    assert window.tab_widget.count() == 5
    assert isinstance(window.roots_tab, RootsTab)
    assert isinstance(window.index_tab, IndexTab)
    assert isinstance(window.search_tab, SearchTab)
    assert isinstance(window.settings_tab, SettingsTab)
    assert isinstance(window.about_tab, AboutTab)
    assert launcher is window.launcher_window
    assert window.launcher_window.parent() is None


def test_app_updates_index_status_in_tab_and_tray(qapp) -> None:
    window = EodingaWindow()
    status = IndexingStatus(phase="indexing", processed_files=12, total_files=40, current_root=Path("/tmp/docs"))

    window.set_indexing_status(status)

    assert window.index_tab.status_chip.text() == "Indexing"
    assert "12/40 files indexed" in window.index_tab.progress_label.text()
    assert "/tmp/docs" in window.tray_indicator.tooltip
    assert "(30%)" in window.tray_indicator.status_text
    assert window.tray_indicator.icon_state == "indexing"

    window.set_indexing_status(IndexingStatus())

    assert window.tray_indicator.icon_state == "idle"


def test_launcher_state_is_shared_between_popup_and_search_tab(qapp) -> None:
    def search_fn(query: str, limit: int) -> QueryResult:
        return QueryResult(
            items=[SearchHit(path=Path("/tmp/release-notes.txt"), parent_path=Path("/tmp"), name="release-notes.txt")][
                :limit
            ],
            total=1,
            elapsed_ms=4.0,
        )

    _, window, launcher = cast(
        tuple[object, EodingaWindow, LauncherWindow],
        launch_gui(test_mode=True, search_fn=search_fn),
    )
    launcher.query_field.setText("release")
    launcher._run_query()

    assert "release" in window.search_tab.launcher_panel.empty_state.body_label.text()
