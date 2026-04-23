from __future__ import annotations

from typing import TYPE_CHECKING, cast

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QKeyEvent

from eodinga.common import SearchHit

if TYPE_CHECKING:
    from eodinga.gui.launcher import LauncherPanel


def handle_query_field_keypress(panel: LauncherPanel, event: QKeyEvent) -> bool:
    if panel.model.rowCount() == 0:
        return False
    if event.key() == Qt.Key.Key_Down:
        panel.result_list.setFocus()
        if not panel.result_list.currentIndex().isValid():
            panel._set_selection(0)
        else:
            move_selection(panel, 1)
        return True
    if event.key() == Qt.Key.Key_Up:
        panel.result_list.setFocus()
        if not panel.result_list.currentIndex().isValid():
            panel._set_selection(panel.model.rowCount() - 1)
        else:
            move_selection(panel, -1)
        return True
    if event.key() == Qt.Key.Key_Home:
        panel.result_list.setFocus()
        panel._set_selection(0)
        return True
    if event.key() == Qt.Key.Key_End:
        panel.result_list.setFocus()
        panel._set_selection(panel.model.rowCount() - 1)
        return True
    if event.key() == Qt.Key.Key_PageDown:
        panel.result_list.setFocus()
        move_selection(panel, page_step(panel))
        return True
    if event.key() == Qt.Key.Key_PageUp:
        panel.result_list.setFocus()
        move_selection(panel, -page_step(panel))
        return True
    if event.key() in {Qt.Key.Key_Tab, Qt.Key.Key_Backtab}:
        panel.result_list.setFocus()
        current_index = panel.result_list.currentIndex()
        if not current_index.isValid() and panel.model.rowCount() > 0:
            panel.result_list.setCurrentIndex(cast(QModelIndex, panel.model.index(0, 0)))
        return True
    return False


def handle_result_list_keypress(panel: LauncherPanel, event: QKeyEvent) -> bool:
    if event.key() in {Qt.Key.Key_Tab, Qt.Key.Key_Backtab}:
        panel.query_field.setFocus()
        return True
    if event.key() == Qt.Key.Key_Down:
        move_selection(panel, 1, wrap=True)
        return True
    if event.key() == Qt.Key.Key_Up:
        move_selection(panel, -1, wrap=True)
        return True
    if event.key() == Qt.Key.Key_Home:
        panel._set_selection(0)
        return True
    if event.key() == Qt.Key.Key_End:
        panel._set_selection(panel.model.rowCount() - 1)
        return True
    if event.key() == Qt.Key.Key_PageDown:
        move_selection(panel, page_step(panel))
        return True
    if event.key() == Qt.Key.Key_PageUp:
        move_selection(panel, -page_step(panel))
        return True
    return False


def move_selection(panel: LauncherPanel, delta: int, *, wrap: bool = False) -> None:
    if panel.model.rowCount() == 0:
        return
    current_row = panel.result_list.currentIndex().row()
    if current_row < 0:
        current_row = 0
    if wrap:
        next_row = (current_row + delta) % panel.model.rowCount()
    else:
        next_row = min(max(current_row + delta, 0), panel.model.rowCount() - 1)
    panel._set_selection(next_row)


def page_step(panel: LauncherPanel) -> int:
    return min(max(panel.model.rowCount() // 2, 1), 10)


def restore_selection(panel: LauncherPanel, previous_hit: SearchHit | None) -> None:
    if panel.model.rowCount() == 0:
        return
    if previous_hit is not None:
        for row, item in enumerate(panel._latest_result.items):
            if item.path == previous_hit.path:
                panel._set_selection(row)
                return
    panel._set_selection(0)


def navigate_recent_queries(panel: LauncherPanel, direction: int) -> None:
    if not panel._recent_queries:
        return
    if direction < 0:
        if panel._history_index is None:
            panel._history_draft = panel.query_field.text()
            next_index = 0
        else:
            next_index = min(panel._history_index + 1, len(panel._recent_queries) - 1)
    else:
        if panel._history_index is None:
            return
        if panel._history_index == 0:
            panel._history_index = None
            set_query_from_history(panel, panel._history_draft)
            panel._history_draft = ""
            return
        next_index = panel._history_index - 1
    panel._history_index = next_index
    set_query_from_history(panel, panel._recent_queries[next_index])


def set_query_from_history(panel: LauncherPanel, query: str) -> None:
    panel._applying_history_query = True
    try:
        panel._skip_remember_query = True
        panel.query_field.setFocus()
        panel.query_field.setText(query)
        panel.query_field.setCursorPosition(len(query))
    finally:
        panel._applying_history_query = False
