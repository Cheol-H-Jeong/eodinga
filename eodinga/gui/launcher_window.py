from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QCloseEvent, QHideEvent, QKeyEvent, QMoveEvent, QResizeEvent, QShowEvent

from eodinga.config import AppConfig
from eodinga.gui.launcher import LauncherPanel, LauncherState, SearchFn


class LauncherWindow(LauncherPanel):
    def __init__(
        self,
        search_fn: SearchFn | None = None,
        max_results: int = 200,
        state: LauncherState | None = None,
        config: AppConfig | None = None,
        config_path: Path | None = None,
        parent=None,
    ) -> None:
        super().__init__(search_fn=search_fn, max_results=max_results, state=state, parent=parent)
        self._config = config
        self._config_path = config_path.expanduser() if config_path is not None else None
        self._geometry_restored = False
        self._geometry_save_timer = QTimer(self)
        self._geometry_save_timer.setSingleShot(True)
        self._geometry_save_timer.setInterval(150)
        self._geometry_save_timer.timeout.connect(self._persist_geometry)
        self.setObjectName("surface")
        self.setAccessibleName("Launcher window")
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowType.Tool, True)
        always_on_top = self._config.launcher.always_on_top if self._config is not None else False
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, always_on_top)
        width = self._config.launcher.window_width if self._config is not None else 640
        height = self._config.launcher.window_height if self._config is not None else 480
        self.resize(width, height)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            event.accept()
            return
        super().keyPressEvent(event)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if not self._geometry_restored and self._config is not None:
            if self._config.launcher.window_x is not None and self._config.launcher.window_y is not None:
                self.move(self._config.launcher.window_x, self._config.launcher.window_y)
            self._geometry_restored = True
        self.query_field.setFocus()
        self.query_field.selectAll()

    def moveEvent(self, event: QMoveEvent) -> None:
        super().moveEvent(event)
        self._schedule_geometry_persist()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._schedule_geometry_persist()

    def hideEvent(self, event: QHideEvent) -> None:
        self._persist_geometry()
        super().hideEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._persist_geometry()
        super().closeEvent(event)

    def _schedule_geometry_persist(self) -> None:
        if self._config is None or self._config_path is None or not self._geometry_restored or not self.isVisible():
            return
        self._geometry_save_timer.start()

    def _persist_geometry(self) -> None:
        if self._config is None or self._config_path is None or not self._geometry_restored:
            return
        geometry = {
            "window_x": self.x(),
            "window_y": self.y(),
            "window_width": self.width(),
            "window_height": self.height(),
        }
        if (
            self._config.launcher.window_x == geometry["window_x"]
            and self._config.launcher.window_y == geometry["window_y"]
            and self._config.launcher.window_width == geometry["window_width"]
            and self._config.launcher.window_height == geometry["window_height"]
        ):
            return
        self._config.launcher = self._config.launcher.model_copy(update=geometry)
        self._config.save(self._config_path)
