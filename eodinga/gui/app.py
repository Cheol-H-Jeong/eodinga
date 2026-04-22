from __future__ import annotations

import sys
from typing import Literal, cast, overload

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMainWindow, QMenu, QStyle, QSystemTrayIcon, QTabWidget, QVBoxLayout, QWidget

from eodinga.common import IndexingStatus
from eodinga.gui.launcher import LauncherState, LauncherWindow, SearchFn, format_indexing_status
from eodinga.gui.tabs import AboutTab, IndexTab, RootsTab, SearchTab, SettingsTab
from eodinga.gui.theme import apply_theme


class TrayIndicatorController:
    def __init__(self, app: QApplication, launcher_window: LauncherWindow, parent: QWidget) -> None:
        self._tray: QSystemTrayIcon | None = None
        self.tooltip = format_indexing_status(IndexingStatus())
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        icon = app.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView)
        tray = QSystemTrayIcon(icon, parent)
        menu = QMenu(parent)
        show_launcher = QAction("Show launcher", menu)
        show_launcher.triggered.connect(launcher_window.show)
        menu.addAction(show_launcher)
        tray.setContextMenu(menu)
        tray.setToolTip(self.tooltip)
        tray.show()
        self._tray = tray

    @property
    def visible(self) -> bool:
        return self._tray is not None and self._tray.isVisible()

    def set_indexing_status(self, status: IndexingStatus) -> None:
        self.tooltip = format_indexing_status(status)
        if self._tray is not None:
            self._tray.setToolTip(self.tooltip)


class EodingaWindow(QMainWindow):
    def __init__(self, search_fn: SearchFn | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("eodinga")
        self.resize(960, 640)
        self.launcher_state = LauncherState(self)
        self.launcher_window = LauncherWindow(search_fn=search_fn, state=self.launcher_state)

        container = QWidget(self)
        layout = QVBoxLayout(container)
        self.tab_widget = QTabWidget(container)

        self.roots_tab = RootsTab(self)
        self.index_tab = IndexTab(self)
        self.search_tab = SearchTab(search_fn=search_fn, state=self.launcher_state, parent=self)
        self.settings_tab = SettingsTab(self)
        self.about_tab = AboutTab(self)

        self.tab_widget.addTab(self.roots_tab, "Roots")
        self.tab_widget.addTab(self.index_tab, "Index")
        self.tab_widget.addTab(self.search_tab, "Search")
        self.tab_widget.addTab(self.settings_tab, "Settings")
        self.tab_widget.addTab(self.about_tab, "About")

        layout.addWidget(self.tab_widget)
        self.setCentralWidget(container)

        app = cast(QApplication, QApplication.instance())
        self.tray_indicator = TrayIndicatorController(app, self.launcher_window, self)
        self.launcher_state.indexing_status_changed.connect(self.index_tab.set_indexing_status)
        self.launcher_state.indexing_status_changed.connect(self.tray_indicator.set_indexing_status)
        self.set_indexing_status(IndexingStatus())

    def set_indexing_status(self, status: IndexingStatus) -> None:
        self.launcher_state.set_indexing_status(status)


@overload
def launch_gui(
    test_mode: Literal[True],
    search_fn: SearchFn | None = None,
) -> tuple[QApplication, EodingaWindow, LauncherWindow]: ...


@overload
def launch_gui(
    test_mode: Literal[False] = False,
    search_fn: SearchFn | None = None,
) -> int: ...


def launch_gui(
    test_mode: bool = False,
    search_fn: SearchFn | None = None,
) -> tuple[QApplication, EodingaWindow, LauncherWindow] | int:
    app = cast(QApplication, QApplication.instance() or QApplication(sys.argv))
    apply_theme(app, "light")
    window = EodingaWindow(search_fn=search_fn)
    window.show()
    window.launcher_window.hide()
    if test_mode:
        return app, window, window.launcher_window
    return app.exec()
