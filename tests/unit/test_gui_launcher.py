from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from eodinga.common import IndexingStatus, QueryResult, SearchHit
from eodinga.gui.launcher import LauncherState, LauncherWindow


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
    assert "24/120" in launcher.empty_state.details_label.text()

    launcher.query_field.setText("missing")
    _wait(60)

    assert launcher.status_chip.text() == "No results"
    assert launcher.empty_state.title_label.text() == 'No results for "missing"'
    assert "date:this-week" in launcher.empty_state.body_label.text()
    assert "/tmp/archive" in launcher.empty_state.details_label.text()


def test_launcher_empty_state_shows_recent_queries_from_shared_state(qapp) -> None:
    state = LauncherState()
    launcher = LauncherWindow(state=state)
    launcher.show()

    state.remember_query("report")
    state.remember_query("budget")

    assert "budget, report" in launcher.empty_state.body_label.text()
