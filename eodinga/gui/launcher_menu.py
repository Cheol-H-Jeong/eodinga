from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QMenu, QWidget


def build_result_context_menu(
    parent: QWidget,
    *,
    open_result: Callable[[], None],
    reveal_result: Callable[[], None],
    show_properties: Callable[[], None],
    copy_path: Callable[[], None],
    copy_name: Callable[[], None],
) -> QMenu:
    menu = QMenu(parent)
    specs = [
        ("Open", open_result),
        ("Reveal in folder", reveal_result),
        ("Show properties", show_properties),
        ("Copy path", copy_path),
        ("Copy name", copy_name),
    ]
    for label, callback in specs:
        action = menu.addAction(label)
        action.triggered.connect(callback)
    return menu
