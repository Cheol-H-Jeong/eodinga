from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from typing import Any


def handle_query_field_keypress(panel: Any, event: QKeyEvent) -> bool:
    if panel.model.rowCount() == 0:
        return False
    if event.key() == Qt.Key.Key_Down:
        panel.result_list.setFocus()
        if not panel.result_list.currentIndex().isValid():
            panel._set_selection(0)
        else:
            panel._move_selection(1)
        return True
    if event.key() == Qt.Key.Key_Up:
        panel.result_list.setFocus()
        if not panel.result_list.currentIndex().isValid():
            panel._set_selection(panel.model.rowCount() - 1)
        else:
            panel._move_selection(-1)
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
        panel._move_selection(panel._page_step())
        return True
    if event.key() == Qt.Key.Key_PageUp:
        panel.result_list.setFocus()
        panel._move_selection(-panel._page_step())
        return True
    if event.key() in {Qt.Key.Key_Tab, Qt.Key.Key_Backtab}:
        panel.result_list.setFocus()
        current_index = panel.result_list.currentIndex()
        if not current_index.isValid() and panel.model.rowCount() > 0:
            panel.result_list.setCurrentIndex(panel.model.index(0, 0))
        return True
    return False


def handle_result_list_keypress(panel: Any, event: QKeyEvent) -> bool:
    if event.key() in {Qt.Key.Key_Tab, Qt.Key.Key_Backtab}:
        panel.query_field.setFocus()
        return True
    if event.key() == Qt.Key.Key_Down:
        panel._move_selection(1, wrap=True)
        return True
    if event.key() == Qt.Key.Key_Up:
        panel._move_selection(-1, wrap=True)
        return True
    if event.key() == Qt.Key.Key_Home:
        panel._set_selection(0)
        return True
    if event.key() == Qt.Key.Key_End:
        panel._set_selection(panel.model.rowCount() - 1)
        return True
    if event.key() == Qt.Key.Key_PageDown:
        panel._move_selection(panel._page_step())
        return True
    if event.key() == Qt.Key.Key_PageUp:
        panel._move_selection(-panel._page_step())
        return True
    return False


__all__ = ["handle_query_field_keypress", "handle_result_list_keypress"]
