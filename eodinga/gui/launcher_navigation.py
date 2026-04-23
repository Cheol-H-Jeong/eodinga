from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent


def handle_query_field_keypress(panel: Any, event: QKeyEvent) -> bool:
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
            panel.result_list.setCurrentIndex(panel.model.index(0, 0))
        return True
    return False


def handle_result_list_keypress(panel: Any, event: QKeyEvent) -> bool:
    if event.key() == Qt.Key.Key_Menu or (
        event.key() == Qt.Key.Key_F10 and event.modifiers() == Qt.KeyboardModifier.ShiftModifier
    ):
        return panel.result_context_menu.show_for_current(panel.result_list, panel._current_hit)
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


def move_selection(panel: Any, delta: int, *, wrap: bool = False) -> None:
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


def page_step(panel: Any) -> int:
    return min(max(panel.model.rowCount() // 2, 1), 10)


__all__ = ["handle_query_field_keypress", "handle_result_list_keypress"]
