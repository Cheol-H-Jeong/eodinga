from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMenu, QWidget


def build_result_context_menu(
    parent: QWidget,
    *,
    activate_current_result: Callable[[], None],
    emit_open_containing_folder: Callable[[], None],
    emit_copy_path: Callable[[], None],
    emit_copy_name: Callable[[], None],
    emit_show_properties: Callable[[], None],
) -> QMenu:
    menu = QMenu(parent)
    for label, shortcut, callback in (
        ("Open", "Return", activate_current_result),
        ("Reveal", "Ctrl+Return", emit_open_containing_folder),
        ("Copy Path", "Alt+C", emit_copy_path),
        ("Copy Name", "Alt+N", emit_copy_name),
        ("Properties", "Shift+Return", emit_show_properties),
    ):
        action = QAction(label, menu)
        action.setShortcut(QKeySequence(shortcut))
        action.setShortcutVisibleInContextMenu(True)
        action.triggered.connect(callback)
        menu.addAction(action)
    return menu


__all__ = ["build_result_context_menu"]
