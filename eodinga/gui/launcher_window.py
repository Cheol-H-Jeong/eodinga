from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtCore import QRect, QTimer, Qt, Signal
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
        self.setWindowFlag(Qt.WindowType.Tool, True)
        frameless = self._config.launcher.frameless if self._config is not None else True
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, frameless)
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
        self._set_window_flag_preserving_visibility(Qt.WindowType.WindowStaysOnTopHint, enabled)

    def set_frameless(self, enabled: bool) -> None:
        self._set_window_flag_preserving_visibility(Qt.WindowType.FramelessWindowHint, enabled)

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

    def _set_window_flag_preserving_visibility(self, flag: Qt.WindowType, enabled: bool) -> None:
        current = bool(self.windowFlags() & flag)
        if current == enabled:
            return
        was_visible = self.isVisible()
        geometry = self.geometry()
        self.setWindowFlag(flag, enabled)
        if not was_visible:
            return
        self.show()
        self.setGeometry(self._clamp_geometry(geometry))
        self.raise_()
        self.activateWindow()

    def _restore_geometry(self) -> None:
        if self._config is None:
            return
        launcher = self._config.launcher
        if launcher.window_x is None or launcher.window_y is None:
            return
        self.setGeometry(
            self._clamp_geometry(
                QRect(
                    launcher.window_x,
                    launcher.window_y,
                    launcher.window_width,
                    launcher.window_height,
                )
            )
        )

    def _available_geometry(self) -> QRect:
        screen = self.screen()
        if screen is None:
            app = cast(QApplication | None, QApplication.instance())
            screen = app.primaryScreen() if app is not None else None
        if screen is None:
            return QRect(0, 0, max(self.width(), 1), max(self.height(), 1))
        return screen.availableGeometry()

    def _clamp_geometry(self, geometry: QRect) -> QRect:
        available = self._available_geometry()
        width = min(max(geometry.width(), 1), max(available.width(), 1))
        height = min(max(geometry.height(), 1), max(available.height(), 1))
        max_x = available.x() + max(available.width() - width, 0)
        max_y = available.y() + max(available.height() - height, 0)
        x = min(max(geometry.x(), available.x()), max_x)
        y = min(max(geometry.y(), available.y()), max_y)
        return QRect(x, y, width, height)

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
