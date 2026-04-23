from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QMenu, QWidget


def build_result_menu(
    parent: QWidget,
    *,
    open_result: Callable[[], None],
    reveal_result: Callable[[], None],
    copy_path: Callable[[], None],
    copy_name: Callable[[], None],
    show_properties: Callable[[], None],
) -> QMenu:
    menu = QMenu(parent)
    menu.addAction("Open", open_result)
    menu.addAction("Reveal in folder", reveal_result)
    menu.addSeparator()
    menu.addAction("Copy path", copy_path)
    menu.addAction("Copy name", copy_name)
    menu.addSeparator()
    menu.addAction("Properties", show_properties)
    return menu
