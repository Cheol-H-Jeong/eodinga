from __future__ import annotations

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from eodinga.gui.launcher import LauncherState
from eodinga.gui.launcher_window import LauncherWindow


def _wait(milliseconds: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(milliseconds, loop.quit)
    loop.exec()


def test_launcher_tabs_into_query_chips_when_no_results(qapp) -> None:
    state = LauncherState(pinned_queries=["ext:pdf", "date:this-week"])
    state.remember_query("budget")
    launcher = LauncherWindow(state=state)
    launcher.show()
    _wait(10)

    assert launcher.query_field.hasFocus()

    QTest.keyClick(launcher.query_field, Qt.Key.Key_Tab)
    _wait(10)
    assert launcher.pinned_queries_row.buttons[0].hasFocus()
    assert "Enter applies the highlighted query chip" in launcher.shortcut_label.text()

    QTest.keyClick(launcher.pinned_queries_row.buttons[0], Qt.Key.Key_Right)
    _wait(10)
    assert launcher.pinned_queries_row.buttons[1].hasFocus()

    QTest.keyClick(launcher.pinned_queries_row.buttons[1], Qt.Key.Key_Left)
    _wait(10)
    assert launcher.pinned_queries_row.buttons[0].hasFocus()

def test_launcher_backtab_prefers_recent_chips_when_only_recent_queries_exist(qapp) -> None:
    state = LauncherState()
    state.remember_query("alpha")
    state.remember_query("beta")
    launcher = LauncherWindow(state=state)
    launcher.show()

    QTest.keyClick(launcher.query_field, Qt.Key.Key_Backtab)
    _wait(10)
    assert launcher.recent_queries_row.buttons[-1].hasFocus()

    QTest.keyClick(launcher.recent_queries_row.buttons[-1], Qt.Key.Key_Left)
    _wait(10)
    assert launcher.recent_queries_row.buttons[0].hasFocus()


def test_launcher_search_field_accessibility_reflects_chips_and_filters(qapp) -> None:
    state = LauncherState(pinned_queries=["ext:pdf"])
    state.remember_query("budget")
    launcher = LauncherWindow(state=state)
    launcher.show()
    _wait(10)

    assert "Press Tab or Shift+Tab to focus launcher query chips." in launcher.query_field.accessibleDescription()

    launcher.query_field.setText("ext:pdf date:today")
    _wait(10)

    assert launcher.query_field.accessibleDescription() == (
        "Type a filename, path, or content term to search the index. Active filters: ext:pdf, date:today."
    )
