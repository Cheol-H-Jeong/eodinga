from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, QRect, Qt, Signal
from PySide6.QtGui import QCloseEvent, QGuiApplication, QHideEvent, QMoveEvent, QResizeEvent, QShowEvent

from eodinga.config import AppConfig
from eodinga.gui.design import MOTION_DEBOUNCE_MS
from eodinga.gui.launcher import LauncherPanel, LauncherState, SearchFn


class LauncherWindow(LauncherPanel):
    visibility_changed = Signal(bool)
    _MIN_WIDTH = 320
    _MIN_HEIGHT = 240

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
            restored = self._restored_geometry()
            if restored is not None:
                self.setGeometry(restored)
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

    def _restored_geometry(self) -> QRect | None:
        if self._config is None:
            return None
        x = self._config.launcher.window_x
        y = self._config.launcher.window_y
        if x is None or y is None:
            return None
        candidate = QRect(
            x,
            y,
            max(self._config.launcher.window_width, self._MIN_WIDTH),
            max(self._config.launcher.window_height, self._MIN_HEIGHT),
        )
        return self._clamp_geometry_to_screens(candidate)

    def _clamp_geometry_to_screens(self, geometry: QRect) -> QRect:
        available_screens = self._available_screen_geometries()
        if not available_screens:
            return geometry
        if any(screen.intersects(geometry) for screen in available_screens):
            return geometry
        target = self._closest_screen_geometry(geometry, available_screens)
        width = min(max(geometry.width(), self._MIN_WIDTH), target.width())
        height = min(max(geometry.height(), self._MIN_HEIGHT), target.height())
        x = min(max(geometry.x(), target.left()), target.right() - width + 1)
        y = min(max(geometry.y(), target.top()), target.bottom() - height + 1)
        return QRect(x, y, width, height)

    def _available_screen_geometries(self) -> list[QRect]:
        return [screen.availableGeometry() for screen in QGuiApplication.screens()]

    def _closest_screen_geometry(self, geometry: QRect, screens: list[QRect]) -> QRect:
        center = geometry.center()
        return min(
            screens,
            key=lambda rect: (rect.center().x() - center.x()) ** 2 + (rect.center().y() - center.y()) ** 2,
        )
