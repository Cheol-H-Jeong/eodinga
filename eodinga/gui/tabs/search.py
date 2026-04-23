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
        self.setAccessibleDescription("Contains the embedded launcher for searching, previewing, and acting on indexed results.")
        layout = QVBoxLayout(self)
        self.launcher_panel = LauncherPanel(
            search_fn=search_fn,
            max_results=max_results,
            debounce_ms=debounce_ms,
            state=state,
            parent=self,
        )
        self.launcher_panel.setAccessibleDescription(
            "Embedded launcher with query field, result list, action bar, and preview pane."
        )
        layout.addWidget(self.launcher_panel)
