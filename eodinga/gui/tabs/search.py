from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from eodinga.gui.launcher import LauncherPanel, SearchFn


class SearchTab(QWidget):
    def __init__(self, search_fn: SearchFn | None = None, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.launcher_panel = LauncherPanel(search_fn=search_fn, parent=self)
        layout.addWidget(self.launcher_panel)

