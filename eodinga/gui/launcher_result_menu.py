from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QListView
from PySide6.QtWidgets import QMenu, QWidget

from eodinga.common import SearchHit

ActionHandler = Callable[[], None]


class LauncherResultMenuTarget(Protocol):
    result_list: QListView

    def _flush_pending_query(self) -> None: ...
    def _set_selection(self, row: int) -> None: ...
    def _current_hit(self) -> SearchHit | None: ...
    def activate_current_result(self) -> None: ...
    def emit_open_containing_folder(self) -> None: ...
    def emit_copy_path(self) -> None: ...
    def emit_copy_name(self) -> None: ...
    def emit_show_properties(self) -> None: ...


def build_launcher_result_menu(
    parent: QWidget,
    hit: SearchHit,
    *,
    open_result: ActionHandler,
    reveal_result: ActionHandler,
    copy_path: ActionHandler,
    copy_name: ActionHandler,
    show_properties: ActionHandler,
) -> QMenu:
    menu = QMenu(parent)
    menu.setAccessibleName("Launcher result menu")
    menu.setAccessibleDescription(
        f"Actions for {hit.name}: open, reveal, copy path, copy name, and show properties."
    )
    for label, handler in (
        ("Open", open_result),
        ("Reveal", reveal_result),
        ("Copy Path", copy_path),
        ("Copy Name", copy_name),
        ("Properties", show_properties),
    ):
        action = menu.addAction(label)
        action.triggered.connect(handler)
    return menu


def build_launcher_result_menu_for_target(
    target: LauncherResultMenuTarget,
    index: QModelIndex | None = None,
) -> QMenu | None:
    target._flush_pending_query()
    if index is not None and index.isValid():
        target._set_selection(index.row())
    hit = target._current_hit()
    if hit is None:
        return None
    return build_launcher_result_menu(
        target.result_list,
        hit,
        open_result=target.activate_current_result,
        reveal_result=target.emit_open_containing_folder,
        copy_path=target.emit_copy_path,
        copy_name=target.emit_copy_name,
        show_properties=target.emit_show_properties,
    )

__all__ = ["build_launcher_result_menu", "build_launcher_result_menu_for_target"]
