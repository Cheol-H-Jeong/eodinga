from __future__ import annotations

import sys
from typing import cast

from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget, QVBoxLayout, QWidget

from eodinga.gui.launcher import SearchFn
from eodinga.gui.tabs import AboutTab, IndexTab, RootsTab, SearchTab, SettingsTab
from eodinga.gui.theme import apply_theme


class EodingaWindow(QMainWindow):
    def __init__(self, search_fn: SearchFn | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("eodinga")
        self.resize(960, 640)

        container = QWidget(self)
        layout = QVBoxLayout(container)
        self.tab_widget = QTabWidget(container)

        self.roots_tab = RootsTab(self)
        self.index_tab = IndexTab(self)
        self.search_tab = SearchTab(search_fn=search_fn, parent=self)
        self.settings_tab = SettingsTab(self)
        self.about_tab = AboutTab(self)

        self.tab_widget.addTab(self.roots_tab, "Roots")
        self.tab_widget.addTab(self.index_tab, "Index")
        self.tab_widget.addTab(self.search_tab, "Search")
        self.tab_widget.addTab(self.settings_tab, "Settings")
        self.tab_widget.addTab(self.about_tab, "About")

        layout.addWidget(self.tab_widget)
        self.setCentralWidget(container)


def launch_gui(test_mode: bool = False, search_fn: SearchFn | None = None) -> tuple[QApplication, EodingaWindow] | int:
    app = cast(QApplication, QApplication.instance() or QApplication(sys.argv))
    apply_theme(app, "light")
    window = EodingaWindow(search_fn=search_fn)
    window.show()
    if test_mode:
        return app, window
    return app.exec()
