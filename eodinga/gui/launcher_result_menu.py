from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMenu, QWidget

from eodinga.common import SearchHit

ActionHandler = Callable[[], None]


def build_launcher_result_menu(
    parent: QWidget,
    hit: SearchHit | None,
    *,
    open_result: ActionHandler,
    reveal_result: ActionHandler,
    copy_path: ActionHandler,
    copy_name: ActionHandler,
    show_properties: ActionHandler,
) -> QMenu | None:
    if hit is None:
        return None
    menu = QMenu(parent)
    _add_action(menu, "Open", "Return", open_result)
    _add_action(menu, "Reveal", "Ctrl+Return", reveal_result)
    menu.addSeparator()
    _add_action(menu, "Copy Path", "Alt+C", copy_path)
    _add_action(menu, "Copy Name", "Alt+N", copy_name)
    menu.addSeparator()
    _add_action(menu, "Properties", "Shift+Return", show_properties)
    return menu


def _add_action(menu: QMenu, text: str, shortcut: str, handler: ActionHandler) -> QAction:
    action = menu.addAction(text)
    action.setShortcut(QKeySequence(shortcut))
    action.triggered.connect(handler)
    return action


__all__ = ["build_launcher_result_menu"]
