from __future__ import annotations

from typing import Protocol, cast

from PySide6.QtCore import QObject, QPoint, Qt
from PySide6.QtWidgets import QListView, QMenu, QWidget

from eodinga.common import SearchHit


class _LauncherPanelLike(Protocol):
    result_list: QListView

    def activate_current_result(self) -> None: ...
    def emit_open_containing_folder(self) -> None: ...
    def emit_copy_path(self) -> None: ...
    def emit_copy_name(self) -> None: ...
    def emit_show_properties(self) -> None: ...


class LauncherResultContextMenu(QObject):
    def __init__(self, panel: _LauncherPanelLike, parent: QWidget) -> None:
        super().__init__(parent)
        self._panel = panel
        self._menu = QMenu(parent)
        self._open_action = self._menu.addAction("Open")
        self._reveal_action = self._menu.addAction("Reveal")
        self._copy_path_action = self._menu.addAction("Copy Path")
        self._copy_name_action = self._menu.addAction("Copy Name")
        self._properties_action = self._menu.addAction("Properties")
        self._open_action.triggered.connect(panel.activate_current_result)
        self._reveal_action.triggered.connect(panel.emit_open_containing_folder)
        self._copy_path_action.triggered.connect(panel.emit_copy_path)
        self._copy_name_action.triggered.connect(panel.emit_copy_name)
        self._properties_action.triggered.connect(panel.emit_show_properties)
        panel.result_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        panel.result_list.customContextMenuRequested.connect(self.show_for_position)

    def show_for_position(self, pos: QPoint) -> None:
        index = self._panel.result_list.indexAt(pos)
        if index.isValid():
            self._panel.result_list.setCurrentIndex(index)
        has_hit = self._current_hit() is not None
        for action in (
            self._open_action,
            self._reveal_action,
            self._copy_path_action,
            self._copy_name_action,
            self._properties_action,
        ):
            action.setEnabled(has_hit)
        if not has_hit:
            return
        self._menu.popup(self._panel.result_list.viewport().mapToGlobal(pos))

    def _current_hit(self) -> SearchHit | None:
        index = self._panel.result_list.currentIndex()
        if not index.isValid():
            return None
        return cast(SearchHit | None, index.data(Qt.ItemDataRole.UserRole))


__all__ = ["LauncherResultContextMenu"]
