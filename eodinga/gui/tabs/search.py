from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from eodinga.gui.launcher import LauncherPanel, LauncherState, SearchFn


class SearchTab(QWidget):
    def __init__(
        self,
        search_fn: SearchFn | None = None,
        max_results: int = 200,
        debounce_ms: int = 30,
        state: LauncherState | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setAccessibleName("Search tab")
        layout = QVBoxLayout(self)
        self.launcher_panel = LauncherPanel(
            search_fn=search_fn,
            max_results=max_results,
            debounce_ms=debounce_ms,
            state=state,
            parent=self,
        )
        layout.addWidget(self.launcher_panel)
