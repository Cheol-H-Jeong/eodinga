from __future__ import annotations

from contextlib import closing
import sys
from typing import Literal, Protocol, cast, overload

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMainWindow, QMenu, QStyle, QSystemTrayIcon, QTabWidget, QVBoxLayout, QWidget

from eodinga.common import IndexingStatus, QueryResult, SearchHit
from eodinga.config import AppConfig
from eodinga.gui.actions import DesktopActions
from eodinga.gui.launcher import LauncherState, LauncherWindow, SearchFn, format_indexing_status
from eodinga.gui.launcher import LauncherPanel
from eodinga.gui.tabs import AboutTab, IndexTab, RootsTab, SearchTab, SettingsTab
from eodinga.gui.theme import apply_theme
from eodinga.index.storage import open_index
from eodinga.query import QuerySyntaxError, search as run_search


class _DesktopActionsLike(Protocol):
    def open_hit(self, hit: SearchHit) -> None: ...
    def reveal_hit(self, hit: SearchHit) -> None: ...
    def show_properties(self, hit: SearchHit) -> None: ...
    def copy_hit_path(self, hit: SearchHit) -> None: ...
    def copy_hit_name(self, hit: SearchHit) -> None: ...


class TrayIndicatorController:
    def __init__(self, app: QApplication, launcher_window: LauncherWindow, parent: QWidget) -> None:
        self._app = app
        self._launcher_window = launcher_window
        self._tray: QSystemTrayIcon | None = None
        self.tooltip = format_indexing_status(IndexingStatus())
        self.status_text = self.tooltip
        self.icon_state = "idle"
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        icon = self._icon_for_state(self.icon_state)
        tray = QSystemTrayIcon(icon, parent)
        menu = QMenu(parent)
        self._status_action = QAction(self.status_text, menu)
        self._status_action.setEnabled(False)
        menu.addAction(self._status_action)
        menu.addSeparator()
        show_launcher = QAction("Show launcher", menu)
        show_launcher.triggered.connect(self.show_launcher)
        menu.addAction(show_launcher)
        tray.setContextMenu(menu)
        tray.setToolTip(self.tooltip)
        tray.activated.connect(self._handle_activation)
        tray.show()
        self._tray = tray

    @property
    def visible(self) -> bool:
        return self._tray is not None and self._tray.isVisible()

    def _icon_for_state(self, state: str):
        if state == "indexing":
            return self._app.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        return self._app.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton)

    def set_indexing_status(self, status: IndexingStatus) -> None:
        self.tooltip = format_indexing_status(status)
        self.status_text = self.tooltip
        self.icon_state = "indexing" if status.phase == "indexing" else "idle"
        if hasattr(self, "_status_action"):
            self._status_action.setText(self.status_text)
        if self._tray is not None:
            self._tray.setIcon(self._icon_for_state(self.icon_state))
            self._tray.setToolTip(self.tooltip)

    def show_launcher(self) -> None:
        self._launcher_window.show()
        self._launcher_window.raise_()
        self._launcher_window.activateWindow()
        self._launcher_window.query_field.setFocus()
        self._launcher_window.query_field.selectAll()

    def _handle_activation(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in {
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        }:
            if self._launcher_window.isVisible():
                self._launcher_window.hide()
                return
            self.show_launcher()


class EodingaWindow(QMainWindow):
    def __init__(
        self,
        search_fn: SearchFn | None = None,
        desktop_actions: _DesktopActionsLike | None = None,
        config: AppConfig | None = None,
        config_path=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("eodinga")
        self.resize(960, 640)
        self.launcher_state = LauncherState(self)
        self.launcher_window = LauncherWindow(
            search_fn=search_fn,
            state=self.launcher_state,
            config=config,
            config_path=config_path,
        )

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
        self.desktop_actions = desktop_actions or DesktopActions(app)
        self._connect_launcher_actions(self.launcher_window)
        self._connect_launcher_actions(self.search_tab.launcher_panel)
        self.tray_indicator = TrayIndicatorController(app, self.launcher_window, self)
        self.launcher_state.indexing_status_changed.connect(self.index_tab.set_indexing_status)
        self.launcher_state.indexing_status_changed.connect(self.tray_indicator.set_indexing_status)
        self.set_indexing_status(IndexingStatus())

    def _connect_launcher_actions(self, launcher: LauncherPanel) -> None:
        launcher.result_activated.connect(self.desktop_actions.open_hit)
        launcher.open_containing_folder.connect(self.desktop_actions.reveal_hit)
        launcher.show_properties.connect(self.desktop_actions.show_properties)
        launcher.copy_path_requested.connect(self.desktop_actions.copy_hit_path)
        launcher.copy_name_requested.connect(self.desktop_actions.copy_hit_name)

    def set_indexing_status(self, status: IndexingStatus) -> None:
        self.launcher_state.set_indexing_status(status)


def build_index_search_fn(db_path) -> SearchFn:
    def _search(query: str, limit: int) -> QueryResult:
        normalized = query.strip()
        if not normalized or limit <= 0:
            return QueryResult(items=[], total=0, elapsed_ms=0.0)
        try:
            with closing(open_index(db_path)) as conn:
                result = run_search(conn, normalized, limit=limit)
        except (QuerySyntaxError, ValueError):
            return QueryResult(items=[], total=0, elapsed_ms=0.0)
        items = [
            SearchHit(
                path=hit.file.path,
                parent_path=hit.file.parent_path,
                name=hit.file.name,
                ext=hit.file.ext,
                snippet=hit.snippet,
            )
            for hit in result.hits[:limit]
        ]
        return QueryResult(items=items, total=result.total_estimate, elapsed_ms=result.elapsed_ms)

    return _search


@overload
def launch_gui(
    test_mode: Literal[True],
    search_fn: SearchFn | None = None,
    db_path=None,
    config: AppConfig | None = None,
    config_path=None,
) -> tuple[QApplication, EodingaWindow, LauncherWindow]: ...


@overload
def launch_gui(
    test_mode: Literal[False] = False,
    search_fn: SearchFn | None = None,
    db_path=None,
    config: AppConfig | None = None,
    config_path=None,
) -> int: ...


def launch_gui(
    test_mode: bool = False,
    search_fn: SearchFn | None = None,
    db_path=None,
    config: AppConfig | None = None,
    config_path=None,
) -> tuple[QApplication, EodingaWindow, LauncherWindow] | int:
    app = cast(QApplication, QApplication.instance() or QApplication(sys.argv))
    apply_theme(app, "light")
    if search_fn is None and db_path is not None:
        search_fn = build_index_search_fn(db_path)
    window = EodingaWindow(search_fn=search_fn, config=config, config_path=config_path)
    window.show()
    window.launcher_window.hide()
    if test_mode:
        return app, window, window.launcher_window
    return app.exec()
