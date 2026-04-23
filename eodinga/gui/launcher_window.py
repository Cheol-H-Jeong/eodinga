from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QCloseEvent, QGuiApplication, QHideEvent, QMoveEvent, QResizeEvent, QShowEvent

from eodinga.config import AppConfig
from eodinga.gui.design import MOTION_DEBOUNCE_MS
from eodinga.gui.launcher import LauncherPanel, LauncherState, SearchFn

DEFAULT_WINDOW_WIDTH = 640
DEFAULT_WINDOW_HEIGHT = 480
MIN_WINDOW_WIDTH = 480
MIN_WINDOW_HEIGHT = 320


class LauncherWindow(LauncherPanel):
    visibility_changed = Signal(bool)

    def __init__(
        self,
        search_fn: SearchFn | None = None,
        max_results: int = 200,
        debounce_ms: int = MOTION_DEBOUNCE_MS,
        state: LauncherState | None = None,
        config: AppConfig | None = None,
        config_path: Path | None = None,
        parent=None,
    ) -> None:
        super().__init__(search_fn=search_fn, max_results=max_results, debounce_ms=debounce_ms, state=state, parent=parent)
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
        width = self._config.launcher.window_width if self._config is not None else DEFAULT_WINDOW_WIDTH
        height = self._config.launcher.window_height if self._config is not None else DEFAULT_WINDOW_HEIGHT
        self.resize(width, height)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            event.accept()
            return
        super().keyPressEvent(event)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if not self._geometry_restored and self._config is not None:
            geometry = self._restored_geometry()
            self.resize(geometry["window_width"], geometry["window_height"])
            self.move(geometry["window_x"], geometry["window_y"])
            self._geometry_restored = True
        self.query_field.setFocus()
        self.query_field.selectAll()
        self.visibility_changed.emit(True)

    def moveEvent(self, event: QMoveEvent) -> None:
        super().moveEvent(event)
        self._schedule_geometry_persist()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._schedule_geometry_persist()

    def set_always_on_top(self, enabled: bool) -> None:
        current = bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        if current == enabled:
            return
        was_visible = self.isVisible()
        position = self.pos()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, enabled)
        if was_visible:
            self.show()
            self.move(position)
            self.raise_()
            self.activateWindow()

    def hideEvent(self, event: QHideEvent) -> None:
        self._persist_geometry()
        super().hideEvent(event)
        self.visibility_changed.emit(False)

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

    def _restored_geometry(self) -> dict[str, int]:
        config = cast(AppConfig, self._config)
        app = cast(QGuiApplication | None, QGuiApplication.instance())
        primary_screen = app.primaryScreen() if app is not None else None
        available_geometry = primary_screen.availableGeometry() if primary_screen is not None else None
        config_geometry = config.launcher
        if available_geometry is None:
            return {
                "window_x": config_geometry.window_x or 0,
                "window_y": config_geometry.window_y or 0,
                "window_width": max(config_geometry.window_width, MIN_WINDOW_WIDTH),
                "window_height": max(config_geometry.window_height, MIN_WINDOW_HEIGHT),
            }
        width = min(max(config_geometry.window_width, MIN_WINDOW_WIDTH), available_geometry.width())
        height = min(max(config_geometry.window_height, MIN_WINDOW_HEIGHT), available_geometry.height())
        default_x = available_geometry.left() + max((available_geometry.width() - width) // 2, 0)
        default_y = available_geometry.top() + max((available_geometry.height() - height) // 2, 0)
        if config_geometry.window_x is None or config_geometry.window_y is None:
            return {
                "window_x": default_x,
                "window_y": default_y,
                "window_width": width,
                "window_height": height,
            }
        max_x = max(available_geometry.left(), available_geometry.right() - width + 1)
        max_y = max(available_geometry.top(), available_geometry.bottom() - height + 1)
        return {
            "window_x": min(max(config_geometry.window_x, available_geometry.left()), max_x),
            "window_y": min(max(config_geometry.window_y, available_geometry.top()), max_y),
            "window_width": width,
            "window_height": height,
        }
