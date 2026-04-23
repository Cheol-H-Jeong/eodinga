from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QWidget


class LauncherResultMenu(QMenu):
    def __init__(
        self,
        *,
        on_open: Callable[[], None],
        on_reveal: Callable[[], None],
        on_copy_path: Callable[[], None],
        on_copy_name: Callable[[], None],
        on_properties: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.open_action = QAction("Open", self)
        self.reveal_action = QAction("Reveal", self)
        self.copy_path_action = QAction("Copy Path", self)
        self.copy_name_action = QAction("Copy Name", self)
        self.properties_action = QAction("Properties", self)

        self.open_action.triggered.connect(on_open)
        self.reveal_action.triggered.connect(on_reveal)
        self.copy_path_action.triggered.connect(on_copy_path)
        self.copy_name_action.triggered.connect(on_copy_name)
        self.properties_action.triggered.connect(on_properties)

        self.addAction(self.open_action)
        self.addAction(self.reveal_action)
        self.addSeparator()
        self.addAction(self.copy_path_action)
        self.addAction(self.copy_name_action)
        self.addSeparator()
        self.addAction(self.properties_action)


__all__ = ["LauncherResultMenu"]
