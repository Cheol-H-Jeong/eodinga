from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtCore import QPoint, QRect, QTimer, Qt, Signal
from PySide6.QtGui import QCloseEvent, QHideEvent, QMoveEvent, QResizeEvent, QShowEvent
from PySide6.QtWidgets import QApplication

from eodinga.config import AppConfig
from eodinga.gui.design import MOTION_DEBOUNCE_MS
from eodinga.gui.launcher import LauncherPanel, LauncherState, SearchFn


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
        frameless = self._config.launcher.frameless if self._config is not None else True
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, frameless)
        self.setWindowFlag(Qt.WindowType.Tool, True)
        always_on_top = self._config.launcher.always_on_top if self._config is not None else False
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, always_on_top)
        width = self._config.launcher.window_width if self._config is not None else 640
        height = self._config.launcher.window_height if self._config is not None else 480
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
            self._restore_geometry()
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
        self._apply_window_flag(Qt.WindowType.WindowStaysOnTopHint, enabled)

    def set_frameless(self, enabled: bool) -> None:
        current = bool(self.windowFlags() & Qt.WindowType.FramelessWindowHint)
        if current == enabled:
            return
        self._apply_window_flag(Qt.WindowType.FramelessWindowHint, enabled)

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

    def _apply_window_flag(self, flag: Qt.WindowType, enabled: bool) -> None:
        was_visible = self.isVisible()
        position = self.pos()
        size = self.size()
        self.setWindowFlag(flag, enabled)
        self.resize(size)
        self.move(position)
        if was_visible:
            self.show()
            self.raise_()
            self.activateWindow()

    def _restore_geometry(self) -> None:
        if self._config is None:
            return
        geometry = self._bounded_geometry(
            self._config.launcher.window_x,
            self._config.launcher.window_y,
            self._config.launcher.window_width,
            self._config.launcher.window_height,
        )
        self.resize(geometry.width(), geometry.height())
        final_geometry = self._bounded_geometry(
            self._config.launcher.window_x,
            self._config.launcher.window_y,
            self.width(),
            self.height(),
        )
        self.move(final_geometry.topLeft())

    def _bounded_geometry(self, x: int | None, y: int | None, width: int, height: int) -> QRect:
        available = self._available_geometry_for_point(x, y)
        bounded_width = min(max(320, width), available.width())
        bounded_height = min(max(240, height), available.height())
        max_x = available.x() + max(0, available.width() - bounded_width)
        max_y = available.y() + max(0, available.height() - bounded_height)
        bounded_x = available.x() if x is None else min(max(x, available.x()), max_x)
        bounded_y = available.y() if y is None else min(max(y, available.y()), max_y)
        return QRect(bounded_x, bounded_y, bounded_width, bounded_height)

    def _available_geometry_for_point(self, x: int | None, y: int | None) -> QRect:
        app = cast(QApplication | None, QApplication.instance())
        screen = None
        if app is not None and x is not None and y is not None:
            screen = app.screenAt(QPoint(x, y))
        if screen is None and app is not None:
            screen = app.primaryScreen()
        if screen is None:
            return QRect(0, 0, 640, 480)
        return screen.availableGeometry()
