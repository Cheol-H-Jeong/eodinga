from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QListView, QMenu, QWidget

from eodinga.common import SearchHit


class LauncherResultContextMenu:
    def __init__(
        self,
        *,
        open_result: Callable[[], None],
        reveal_result: Callable[[], None],
        copy_path: Callable[[], None],
        copy_name: Callable[[], None],
        show_properties: Callable[[], None],
        parent: QWidget,
    ) -> None:
        self.menu = QMenu(parent)
        self.open_action = self.menu.addAction("Open")
        self.reveal_action = self.menu.addAction("Reveal")
        self.copy_path_action = self.menu.addAction("Copy path")
        self.copy_name_action = self.menu.addAction("Copy name")
        self.properties_action = self.menu.addAction("Properties")
        self.open_action.triggered.connect(open_result)
        self.reveal_action.triggered.connect(reveal_result)
        self.copy_path_action.triggered.connect(copy_path)
        self.copy_name_action.triggered.connect(copy_name)
        self.properties_action.triggered.connect(show_properties)

    def sync_enabled(self, hit: SearchHit | None) -> bool:
        enabled = hit is not None
        self.open_action.setEnabled(enabled)
        self.reveal_action.setEnabled(enabled)
        self.copy_path_action.setEnabled(enabled)
        self.copy_name_action.setEnabled(enabled)
        self.properties_action.setEnabled(enabled)
        return enabled

    def show_for_current(self, view: QListView, current_hit: Callable[[], SearchHit | None]) -> bool:
        hit = current_hit()
        if not self.sync_enabled(hit):
            return False
        self.menu.popup(view.viewport().mapToGlobal(view.visualRect(view.currentIndex()).center()))
        return True

    def show_for_position(
        self,
        view: QListView,
        position: QPoint,
        *,
        current_hit: Callable[[], SearchHit | None],
        select_row: Callable[[int], None],
    ) -> bool:
        index = view.indexAt(position)
        if index.isValid():
            select_row(index.row())
        hit = current_hit()
        if not self.sync_enabled(hit):
            return False
        self.menu.popup(view.viewport().mapToGlobal(position))
        return True


__all__ = ["LauncherResultContextMenu"]
