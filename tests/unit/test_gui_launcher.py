from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from eodinga.common import IndexingStatus, QueryResult, SearchHit
from eodinga.gui.launcher import LauncherState
from eodinga.gui.launcher_window import LauncherWindow


def _wait(milliseconds: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(milliseconds, loop.quit)
    loop.exec()


def test_launcher_debounces_and_updates_results(qapp) -> None:
    def search_fn(query: str, limit: int) -> QueryResult:
        return QueryResult(
            items=[
                SearchHit(
                    path=Path(f"/tmp/{query}.txt"),
                    parent_path=Path("/tmp"),
                    name=f"{query}.txt",
                    highlighted_name=f"<mark>{query}</mark>.txt",
                    highlighted_path=f"/tmp/<mark>{query}</mark>.txt",
                )
            ],
            total=1,
            elapsed_ms=9.5,
        )

    launcher = LauncherWindow(search_fn=search_fn)
    launcher.show()

    launcher.query_field.setText("report")
    _wait(60)

    assert launcher.model.rowCount() == 1
    assert launcher.status_label.text() == "1 results · 9.5 ms"
    result = launcher.model.item_at(0)
    assert result is not None
    assert result.name == "report.txt"


def test_launcher_keyboard_flow_supports_arrow_navigation_and_tab_return(qapp) -> None:
    activated: list[str] = []
    revealed: list[str] = []

    def search_fn(query: str, limit: int) -> QueryResult:
        return QueryResult(
            items=[
                SearchHit(path=Path("/tmp/alpha.txt"), parent_path=Path("/tmp"), name="alpha.txt"),
                SearchHit(path=Path("/tmp/beta.txt"), parent_path=Path("/tmp"), name="beta.txt"),
            ][:limit],
            total=2,
            elapsed_ms=3.2,
        )

    launcher = LauncherWindow(search_fn=search_fn)
    launcher.result_activated.connect(lambda hit: activated.append(hit.name))
    launcher.open_containing_folder.connect(lambda hit: revealed.append(hit.name))
    launcher.show()

    launcher.query_field.setText("a")
    _wait(60)

    assert launcher.query_field.hasFocus()
    assert launcher.result_list.currentIndex().row() == 0

    QTest.keyClick(launcher.query_field, Qt.Key.Key_Down)

    assert launcher.result_list.hasFocus()
    assert launcher.result_list.currentIndex().row() == 1

    QTest.keyClick(launcher, Qt.Key.Key_Return)
    QTest.keyClick(launcher, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)

    assert activated == ["beta.txt"]
    assert revealed == ["beta.txt"]

    QTest.keyClick(launcher.result_list, Qt.Key.Key_Tab)
    assert launcher.query_field.hasFocus()
    assert "Tab moves to results" in launcher.shortcut_label.text()


def test_launcher_tab_moves_focus_into_results_without_mouse(qapp) -> None:
    def search_fn(query: str, limit: int) -> QueryResult:
        return QueryResult(
            items=[
                SearchHit(path=Path("/tmp/alpha.txt"), parent_path=Path("/tmp"), name="alpha.txt"),
            ][:limit],
            total=1,
            elapsed_ms=1.5,
        )

    launcher = LauncherWindow(search_fn=search_fn)
    launcher.show()

    launcher.query_field.setText("alpha")
    _wait(60)

    assert launcher.query_field.hasFocus()
    QTest.keyClick(launcher.query_field, Qt.Key.Key_Tab)

    assert launcher.result_list.hasFocus()
    assert launcher.result_list.currentIndex().row() == 0


def test_launcher_backtab_and_home_end_support_keyboard_only_navigation(qapp) -> None:
    def search_fn(query: str, limit: int) -> QueryResult:
        return QueryResult(
            items=[
                SearchHit(path=Path("/tmp/alpha.txt"), parent_path=Path("/tmp"), name="alpha.txt"),
                SearchHit(path=Path("/tmp/beta.txt"), parent_path=Path("/tmp"), name="beta.txt"),
                SearchHit(path=Path("/tmp/gamma.txt"), parent_path=Path("/tmp"), name="gamma.txt"),
            ][:limit],
            total=3,
            elapsed_ms=1.5,
        )

    launcher = LauncherWindow(search_fn=search_fn)
    launcher.show()

    launcher.query_field.setText("a")
    _wait(60)

    QTest.keyClick(launcher.query_field, Qt.Key.Key_Backtab)
    assert launcher.result_list.hasFocus()
    assert launcher.result_list.currentIndex().row() == 0
    assert "Ctrl+Enter or Alt+R reveals" in launcher.shortcut_label.text()
    assert "Up/Down wraps" in launcher.shortcut_label.text()
    assert "Home/End and PgUp/PgDn jump" in launcher.shortcut_label.text()
    assert "Ctrl+A or Ctrl+L returns to filter" in launcher.shortcut_label.text()

    QTest.keyClick(launcher.result_list, Qt.Key.Key_End)
    assert launcher.result_list.currentIndex().row() == 2

    QTest.keyClick(launcher.result_list, Qt.Key.Key_Home)
    assert launcher.result_list.currentIndex().row() == 0


def test_launcher_result_list_wraps_with_up_and_down_keys(qapp) -> None:
    def search_fn(query: str, limit: int) -> QueryResult:
        return QueryResult(
            items=[
                SearchHit(path=Path("/tmp/alpha.txt"), parent_path=Path("/tmp"), name="alpha.txt"),
                SearchHit(path=Path("/tmp/beta.txt"), parent_path=Path("/tmp"), name="beta.txt"),
                SearchHit(path=Path("/tmp/gamma.txt"), parent_path=Path("/tmp"), name="gamma.txt"),
            ][:limit],
            total=3,
            elapsed_ms=1.5,
        )

    launcher = LauncherWindow(search_fn=search_fn)
    launcher.show()

    launcher.query_field.setText("a")
    _wait(60)
    launcher.result_list.setFocus()

    QTest.keyClick(launcher.result_list, Qt.Key.Key_Up)
    assert launcher.result_list.currentIndex().row() == 2

    QTest.keyClick(launcher.result_list, Qt.Key.Key_Down)
    assert launcher.result_list.currentIndex().row() == 0


def test_launcher_page_keys_jump_through_results(qapp) -> None:
    def search_fn(query: str, limit: int) -> QueryResult:
        items = [
            SearchHit(path=Path(f"/tmp/item-{index}.txt"), parent_path=Path("/tmp"), name=f"item-{index}.txt")
            for index in range(6)
        ]
        return QueryResult(items=items[:limit], total=len(items), elapsed_ms=1.5)

    launcher = LauncherWindow(search_fn=search_fn)
    launcher.show()

    launcher.query_field.setText("item")
    _wait(60)
    launcher.result_list.setFocus()

    QTest.keyClick(launcher.result_list, Qt.Key.Key_PageDown)
    assert launcher.result_list.currentIndex().row() == 3

    QTest.keyClick(launcher.result_list, Qt.Key.Key_PageDown)
    assert launcher.result_list.currentIndex().row() == 5

    QTest.keyClick(launcher.result_list, Qt.Key.Key_PageUp)
    assert launcher.result_list.currentIndex().row() == 2


def test_launcher_query_field_home_end_and_page_keys_jump_into_results(qapp) -> None:
    def search_fn(query: str, limit: int) -> QueryResult:
        items = [
            SearchHit(path=Path(f"/tmp/item-{index}.txt"), parent_path=Path("/tmp"), name=f"item-{index}.txt")
            for index in range(6)
        ]
        return QueryResult(items=items[:limit], total=len(items), elapsed_ms=1.5)

    launcher = LauncherWindow(search_fn=search_fn)
    launcher.show()

    launcher.query_field.setText("item")
    _wait(60)

    QTest.keyClick(launcher.query_field, Qt.Key.Key_End)
    assert launcher.result_list.hasFocus()
    assert launcher.result_list.currentIndex().row() == 5

    QTest.keyClick(launcher.query_field, Qt.Key.Key_Home)
    assert launcher.result_list.currentIndex().row() == 0

    launcher.query_field.setFocus()
    QTest.keyClick(launcher.query_field, Qt.Key.Key_PageDown)
    assert launcher.result_list.currentIndex().row() == 3

    launcher.query_field.setFocus()
    QTest.keyClick(launcher.query_field, Qt.Key.Key_PageUp)
    assert launcher.result_list.currentIndex().row() == 0


def test_launcher_up_from_query_field_selects_last_result(qapp) -> None:
    def search_fn(query: str, limit: int) -> QueryResult:
        return QueryResult(
            items=[
                SearchHit(path=Path("/tmp/alpha.txt"), parent_path=Path("/tmp"), name="alpha.txt"),
                SearchHit(path=Path("/tmp/beta.txt"), parent_path=Path("/tmp"), name="beta.txt"),
                SearchHit(path=Path("/tmp/gamma.txt"), parent_path=Path("/tmp"), name="gamma.txt"),
            ][:limit],
            total=3,
            elapsed_ms=1.5,
        )

    launcher = LauncherWindow(search_fn=search_fn)
    launcher.show()

    launcher.query_field.setText("a")
    _wait(60)
    launcher.result_list.clearSelection()
    launcher.result_list.setCurrentIndex(launcher.model.index(-1, -1))

    QTest.keyClick(launcher.query_field, Qt.Key.Key_Up)

    assert launcher.result_list.hasFocus()
    assert launcher.result_list.currentIndex().row() == 2


def test_launcher_preserves_selected_result_when_query_refines(qapp) -> None:
    def search_fn(query: str, limit: int) -> QueryResult:
        items = [
            SearchHit(path=Path("/tmp/alpha.txt"), parent_path=Path("/tmp"), name="alpha.txt"),
            SearchHit(path=Path("/tmp/beta.txt"), parent_path=Path("/tmp"), name="beta.txt"),
            SearchHit(path=Path("/tmp/gamma.txt"), parent_path=Path("/tmp"), name="gamma.txt"),
        ]
        if query == "ga":
            items = [items[2]]
        return QueryResult(items=items[:limit], total=len(items), elapsed_ms=1.5)

    launcher = LauncherWindow(search_fn=search_fn)
    launcher.show()

    launcher.query_field.setText("a")
    _wait(60)
    launcher.result_list.setFocus()
    QTest.keyClick(launcher.result_list, Qt.Key.Key_Down)
    QTest.keyClick(launcher.result_list, Qt.Key.Key_Down)

    assert launcher.result_list.currentIndex().row() == 2

    launcher.query_field.setText("ga")
    _wait(60)

    assert launcher.result_list.currentIndex().row() == 0
    result = launcher.model.item_at(0)
    assert result is not None
    assert result.name == "gamma.txt"


def test_launcher_activation_flushes_debounced_query_before_opening(qapp) -> None:
    activated: list[str] = []

    def search_fn(query: str, limit: int) -> QueryResult:
        return QueryResult(
            items=[SearchHit(path=Path("/tmp/report.txt"), parent_path=Path("/tmp"), name="report.txt")][:limit],
            total=1,
            elapsed_ms=2.5,
        )

    launcher = LauncherWindow(search_fn=search_fn)
    launcher.result_activated.connect(lambda hit: activated.append(hit.name))
    launcher.show()

    launcher.query_field.setText("report")
    launcher.activate_current_result()

    assert activated == ["report.txt"]
    assert launcher.model.rowCount() == 1
    assert launcher.status_chip.text() == "Ready"


def test_launcher_shows_clickable_pinned_and_recent_query_chips(qapp) -> None:
    state = LauncherState(pinned_queries=["ext:pdf", "date:this-week"])
    state.remember_query("release notes")
    state.remember_query("budget")
    launcher = LauncherWindow(state=state)
    launcher.show()

    assert [button.text() for button in launcher.pinned_queries_row.buttons] == ["ext:pdf", "date:this-week"]
    assert [button.text() for button in launcher.recent_queries_row.buttons] == ["budget", "release notes"]


def test_launcher_query_chip_applies_query_and_runs_search(qapp) -> None:
    calls: list[str] = []
    state = LauncherState(pinned_queries=["ext:pdf"])

    def search_fn(query: str, limit: int) -> QueryResult:
        calls.append(query)
        return QueryResult(items=[], total=0, elapsed_ms=1.0)

    launcher = LauncherWindow(search_fn=search_fn, state=state)
    launcher.show()

    chip = launcher.pinned_queries_row.buttons[0]
    chip.click()

    assert launcher.query_field.text() == "ext:pdf"
    assert calls == ["ext:pdf"]


def test_launcher_reveal_flushes_debounced_query_before_opening_folder(qapp) -> None:
    revealed: list[str] = []

    def search_fn(query: str, limit: int) -> QueryResult:
        return QueryResult(
            items=[SearchHit(path=Path("/tmp/report.txt"), parent_path=Path("/tmp"), name="report.txt")][:limit],
            total=1,
            elapsed_ms=2.5,
        )

    launcher = LauncherWindow(search_fn=search_fn)
    launcher.open_containing_folder.connect(lambda hit: revealed.append(hit.name))
    launcher.show()

    launcher.query_field.setText("report")
    launcher.emit_open_containing_folder()

    assert revealed == ["report.txt"]
    assert launcher.model.rowCount() == 1


def test_launcher_enter_and_ctrl_enter_work_while_query_field_keeps_focus(qapp) -> None:
    activated: list[str] = []
    revealed: list[str] = []

    def search_fn(query: str, limit: int) -> QueryResult:
        return QueryResult(
            items=[SearchHit(path=Path("/tmp/report.txt"), parent_path=Path("/tmp"), name="report.txt")][:limit],
            total=1,
            elapsed_ms=2.5,
        )

    launcher = LauncherWindow(search_fn=search_fn)
    launcher.result_activated.connect(lambda hit: activated.append(hit.name))
    launcher.open_containing_folder.connect(lambda hit: revealed.append(hit.name))
    launcher.show()

    launcher.query_field.setText("report")
    launcher.query_field.setFocus()
    _wait(10)
    assert launcher.query_field.hasFocus()

    QTest.keyClick(launcher.query_field, Qt.Key.Key_Return)
    QTest.keyClick(launcher.query_field, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)

    assert activated == ["report.txt"]
    assert revealed == ["report.txt"]
    assert launcher.query_field.hasFocus()
    assert launcher.model.rowCount() == 1


def test_launcher_empty_state_reflects_query_results(qapp) -> None:
    def search_fn(query: str, limit: int) -> QueryResult:
        if not query:
            return QueryResult(items=[], total=0, elapsed_ms=1.0)
        return QueryResult(items=[], total=0, elapsed_ms=2.0)

    state = LauncherState()
    state.set_indexing_status(
        IndexingStatus(phase="indexing", processed_files=24, total_files=120, current_root=Path("/tmp/archive"))
    )
    launcher = LauncherWindow(search_fn=search_fn, state=state)
    launcher.show()

    assert launcher.empty_state.title_label.text() == "Type to search"
    assert "No recent queries yet" in launcher.empty_state.body_label.text()
    assert "Alt+Up" in launcher.empty_state.body_label.text()
    assert "Ctrl+Enter" in launcher.empty_state.body_label.text()
    assert "24/120" in launcher.empty_state.details_label.text()
    assert "(20%)" in launcher.empty_state.details_label.text()
    assert launcher.status_chip.text() == "Indexing"
    assert launcher.status_label.text() == "24/120 files · 20% indexed"
    assert launcher.shortcut_label.text() == "Type a filename, path, or content term. Alt+Up recalls recent queries."

    launcher.query_field.setText("missing")
    _wait(60)

    assert launcher.status_chip.text() == "No results"
    assert launcher.empty_state.title_label.text() == 'No results for "missing"'
    assert "date:this-week" in launcher.empty_state.body_label.text()
    assert "Esc to hide the launcher" in launcher.empty_state.body_label.text()
    assert "/tmp/archive" in launcher.empty_state.details_label.text()
    assert "ext:, date:, size:, or content:" in launcher.shortcut_label.text()
    assert "Alt+Up recalls recent queries" in launcher.shortcut_label.text()


def test_launcher_empty_state_shows_recent_queries_from_shared_state(qapp) -> None:
    state = LauncherState()
    launcher = LauncherWindow(state=state)
    launcher.show()

    state.remember_query("report")
    state.remember_query("budget")

    assert "budget, report" in launcher.empty_state.body_label.text()


def test_launcher_empty_state_shows_pinned_queries_from_shared_state(qapp) -> None:
    state = LauncherState(pinned_queries=["ext:pdf", "size:>10M", "ext:pdf"])
    launcher = LauncherWindow(state=state)
    launcher.show()

    assert "Pinned: ext:pdf, size:>10M." in launcher.empty_state.body_label.text()


def test_launcher_ctrl_l_returns_focus_to_query_field_and_selects_text(qapp) -> None:
    def search_fn(query: str, limit: int) -> QueryResult:
        return QueryResult(
            items=[
                SearchHit(path=Path("/tmp/alpha.txt"), parent_path=Path("/tmp"), name="alpha.txt"),
                SearchHit(path=Path("/tmp/beta.txt"), parent_path=Path("/tmp"), name="beta.txt"),
            ][:limit],
            total=2,
            elapsed_ms=1.5,
        )

    launcher = LauncherWindow(search_fn=search_fn)
    launcher.show()

    launcher.query_field.setText("alpha")
    _wait(60)
    launcher.result_list.setFocus()
    QTest.keyClick(launcher.result_list, Qt.Key.Key_Down)

    assert launcher.result_list.hasFocus()
    assert launcher.result_list.currentIndex().row() == 1

    QTest.keyClick(launcher.result_list, Qt.Key.Key_L, Qt.KeyboardModifier.ControlModifier)

    assert launcher.query_field.hasFocus()
    assert launcher.query_field.selectedText() == "alpha"


def test_launcher_ctrl_a_returns_focus_to_query_field_and_selects_text(qapp) -> None:
    def search_fn(query: str, limit: int) -> QueryResult:
        return QueryResult(
            items=[
                SearchHit(path=Path("/tmp/alpha.txt"), parent_path=Path("/tmp"), name="alpha.txt"),
                SearchHit(path=Path("/tmp/beta.txt"), parent_path=Path("/tmp"), name="beta.txt"),
            ][:limit],
            total=2,
            elapsed_ms=1.5,
        )

    launcher = LauncherWindow(search_fn=search_fn)
    launcher.show()

    launcher.query_field.setText("alpha")
    _wait(60)
    launcher.result_list.setFocus()
    QTest.keyClick(launcher.result_list, Qt.Key.Key_Down)

    QTest.keyClick(launcher.result_list, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)

    assert launcher.query_field.hasFocus()
    assert launcher.query_field.selectedText() == "alpha"


def test_launcher_alt_up_and_down_recall_recent_queries(qapp) -> None:
    def search_fn(query: str, limit: int) -> QueryResult:
        return QueryResult(
            items=[SearchHit(path=Path(f"/tmp/{query}.txt"), parent_path=Path("/tmp"), name=f"{query}.txt")][:limit]
            if query
            else [],
            total=1 if query else 0,
            elapsed_ms=2.0,
        )

    launcher = LauncherWindow(search_fn=search_fn, state=LauncherState())
    launcher.show()

    launcher.query_field.setText("alpha")
    _wait(60)
    launcher.query_field.setText("beta")
    _wait(60)
    launcher.query_field.setText("")
    _wait(60)

    QTest.keyClick(launcher.query_field, Qt.Key.Key_Up, Qt.KeyboardModifier.AltModifier)
    _wait(60)
    assert launcher.query_field.text() == "beta"

    QTest.keyClick(launcher.query_field, Qt.Key.Key_Up, Qt.KeyboardModifier.AltModifier)
    _wait(60)
    assert launcher.query_field.text() == "alpha"

    QTest.keyClick(launcher.query_field, Qt.Key.Key_Down, Qt.KeyboardModifier.AltModifier)
    _wait(60)
    assert launcher.query_field.text() == "beta"

    QTest.keyClick(launcher.query_field, Qt.Key.Key_Down, Qt.KeyboardModifier.AltModifier)
    _wait(60)
    assert launcher.query_field.text() == ""


def test_launcher_shortcuts_cover_properties_and_copy_path(qapp) -> None:
    properties: list[str] = []
    copied: list[str] = []
    copied_names: list[str] = []

    def search_fn(query: str, limit: int) -> QueryResult:
        return QueryResult(
            items=[
                SearchHit(
                    path=Path("/tmp/release-notes.txt"),
                    parent_path=Path("/tmp"),
                    name="release-notes.txt",
                )
            ][:limit],
            total=1,
            elapsed_ms=2.0,
        )

    launcher = LauncherWindow(search_fn=search_fn)
    launcher.show_properties.connect(lambda hit: properties.append(hit.name))
    launcher.copy_path_requested.connect(lambda hit: copied.append(str(hit.path)))
    launcher.copy_name_requested.connect(lambda hit: copied_names.append(hit.name))
    launcher.show()

    launcher.query_field.setText("release")
    _wait(60)

    QTest.keyClick(launcher, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    QTest.keyClick(launcher, Qt.Key.Key_C, Qt.KeyboardModifier.AltModifier)
    QTest.keyClick(launcher, Qt.Key.Key_N, Qt.KeyboardModifier.AltModifier)

    assert properties == ["release-notes.txt"]
    assert copied == ["/tmp/release-notes.txt"]
    assert copied_names == ["release-notes.txt"]
    assert "Alt+N copies name" in launcher.shortcut_label.text()


def test_launcher_alt_action_shortcuts_open_reveal_and_show_properties(qapp) -> None:
    activated: list[str] = []
    revealed: list[str] = []
    properties: list[str] = []

    def search_fn(query: str, limit: int) -> QueryResult:
        return QueryResult(
            items=[
                SearchHit(
                    path=Path("/tmp/release-notes.txt"),
                    parent_path=Path("/tmp"),
                    name="release-notes.txt",
                )
            ][:limit],
            total=1,
            elapsed_ms=2.0,
        )

    launcher = LauncherWindow(search_fn=search_fn)
    launcher.result_activated.connect(lambda hit: activated.append(hit.name))
    launcher.open_containing_folder.connect(lambda hit: revealed.append(hit.name))
    launcher.show_properties.connect(lambda hit: properties.append(hit.name))
    launcher.show()

    launcher.query_field.setText("release")
    _wait(60)

    QTest.keyClick(launcher.query_field, Qt.Key.Key_O, Qt.KeyboardModifier.AltModifier)
    QTest.keyClick(launcher.query_field, Qt.Key.Key_R, Qt.KeyboardModifier.AltModifier)
    QTest.keyClick(launcher.query_field, Qt.Key.Key_P, Qt.KeyboardModifier.AltModifier)

    assert activated == ["release-notes.txt"]
    assert revealed == ["release-notes.txt"]
    assert properties == ["release-notes.txt"]
    assert "Alt+O opens the top hit" in launcher.shortcut_label.text()
    assert "Alt+R reveals" in launcher.shortcut_label.text()
    assert "Alt+P shows properties" in launcher.shortcut_label.text()


def test_launcher_preview_tracks_selection_and_hovered_result(qapp) -> None:
    def search_fn(query: str, limit: int) -> QueryResult:
        return QueryResult(
            items=[
                SearchHit(
                    path=Path("/tmp/alpha.txt"),
                    parent_path=Path("/tmp"),
                    name="alpha.txt",
                    snippet="Alpha release notes",
                ),
                SearchHit(
                    path=Path("/tmp/beta.txt"),
                    parent_path=Path("/tmp"),
                    name="beta.txt",
                    snippet="Beta launch checklist",
                ),
            ][:limit],
            total=2,
            elapsed_ms=2.0,
        )

    launcher = LauncherWindow(search_fn=search_fn)
    launcher.show()

    assert launcher.preview_pane.title_label.text() == "No preview yet"
    assert not launcher.action_bar.open_button.isEnabled()

    launcher.query_field.setText("notes")
    _wait(60)

    assert launcher.preview_pane.title_label.text() == "alpha.txt"
    assert "/tmp/alpha.txt" in launcher.preview_pane.path_label.text()
    assert "Alpha release notes" in launcher.preview_pane.snippet_label.text()
    assert launcher.action_bar.open_button.isEnabled()

    launcher._sync_preview_to_index(launcher.model.index(1, 0))

    assert launcher.preview_pane.title_label.text() == "beta.txt"
    assert "Beta launch checklist" in launcher.preview_pane.snippet_label.text()


def test_launcher_action_bar_triggers_result_actions(qapp) -> None:
    activated: list[str] = []
    revealed: list[str] = []
    copied_paths: list[str] = []
    copied_names: list[str] = []
    properties: list[str] = []

    def search_fn(query: str, limit: int) -> QueryResult:
        return QueryResult(
            items=[
                SearchHit(path=Path("/tmp/release-notes.txt"), parent_path=Path("/tmp"), name="release-notes.txt")
            ][:limit],
            total=1,
            elapsed_ms=2.0,
        )

    launcher = LauncherWindow(search_fn=search_fn)
    launcher.result_activated.connect(lambda hit: activated.append(hit.name))
    launcher.open_containing_folder.connect(lambda hit: revealed.append(hit.name))
    launcher.copy_path_requested.connect(lambda hit: copied_paths.append(str(hit.path)))
    launcher.copy_name_requested.connect(lambda hit: copied_names.append(hit.name))
    launcher.show_properties.connect(lambda hit: properties.append(hit.name))
    launcher.show()

    launcher.query_field.setText("release")
    _wait(60)

    launcher.action_bar.open_button.click()
    launcher.action_bar.reveal_button.click()
    launcher.action_bar.copy_path_button.click()
    launcher.action_bar.copy_name_button.click()
    launcher.action_bar.properties_button.click()

    assert activated == ["release-notes.txt"]
    assert revealed == ["release-notes.txt"]
    assert copied_paths == ["/tmp/release-notes.txt"]
    assert copied_names == ["release-notes.txt"]
    assert properties == ["release-notes.txt"]


def test_launcher_alt_number_quick_picks_results(qapp) -> None:
    activated: list[str] = []

    def search_fn(query: str, limit: int) -> QueryResult:
        items = [
            SearchHit(path=Path(f"/tmp/item-{index}.txt"), parent_path=Path("/tmp"), name=f"item-{index}.txt")
            for index in range(5)
        ]
        return QueryResult(items=items[:limit], total=len(items), elapsed_ms=2.0)

    launcher = LauncherWindow(search_fn=search_fn)
    launcher.result_activated.connect(lambda hit: activated.append(hit.name))
    launcher.show()

    launcher.query_field.setText("item")
    _wait(60)
    launcher.query_field.setFocus()

    QTest.keyClick(launcher.query_field, Qt.Key.Key_3, Qt.KeyboardModifier.AltModifier)

    assert activated == ["item-2.txt"]
    assert launcher.result_list.currentIndex().row() == 2
    assert "Alt+1..9 quick-picks" in launcher.shortcut_label.text()
    assert "Home/End and PgUp/PgDn jump" in launcher.shortcut_label.text()


def test_launcher_empty_state_mentions_alt_number_quick_picks(qapp) -> None:
    launcher = LauncherWindow(state=LauncherState())
    launcher.show()

    assert "Alt+1 through Alt+9" in launcher.empty_state.body_label.text()


def test_launcher_accessible_names_cover_keyboard_surface(qapp) -> None:
    launcher = LauncherWindow()
    launcher.show()

    assert launcher.accessibleName() == "Launcher window"
    assert launcher.query_field.accessibleName() == "Launcher search field"
    assert launcher.result_list.accessibleName() == "Launcher results list"
    assert launcher.empty_state.accessibleName() == "Launcher empty state"
    assert launcher.empty_state.title_label.accessibleName() == "Launcher empty state title"
    assert launcher.empty_state.body_label.accessibleName() == "Launcher empty state guidance"
    assert launcher.empty_state.details_label.accessibleName() == "Launcher indexing details"
    assert launcher.preview_pane.accessibleName() == "Launcher preview pane"
    assert launcher.preview_pane.title_label.accessibleName() == "Previewed result name"
    assert launcher.preview_pane.path_label.accessibleName() == "Previewed result path"
    assert launcher.preview_pane.snippet_label.accessibleName() == "Previewed result snippet"
    assert launcher.action_bar.accessibleName() == "Launcher action bar"
    assert launcher.action_bar.open_button.accessibleName() == "Open selected result"
    assert launcher.action_bar.reveal_button.accessibleName() == "Reveal selected result"
    assert launcher.action_bar.copy_path_button.accessibleName() == "Copy selected path"
    assert launcher.action_bar.copy_name_button.accessibleName() == "Copy selected name"
    assert launcher.action_bar.properties_button.accessibleName() == "Show selected properties"
    assert launcher.shortcut_label.accessibleName() == "Launcher shortcut guidance"
    assert launcher.status_label.accessibleName() == "Launcher result summary"
    assert launcher.status_chip.accessibleName() == "Status"
