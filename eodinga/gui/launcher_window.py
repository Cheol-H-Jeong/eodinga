from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtGui import QCloseEvent, QHideEvent, QMoveEvent, QResizeEvent, QShowEvent

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
        self._last_screen_name: str | None = None
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
            self._restore_visible_geometry()
            self._geometry_restored = True
            self._persist_geometry()
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
        self.setGeometry(geometry)
        self.raise_()
        self.activateWindow()
        self._persist_geometry()

    def _persist_geometry(self) -> None:
        if self._config is None or self._config_path is None or not self._geometry_restored:
            return
        geometry = {
            "window_screen": self._current_screen_name(),
            "window_x": self.x(),
            "window_y": self.y(),
            "window_width": self.width(),
            "window_height": self.height(),
        }
        if (
            self._config.launcher.window_screen == geometry["window_screen"]
            and
            self._config.launcher.window_x == geometry["window_x"]
            and self._config.launcher.window_y == geometry["window_y"]
            and self._config.launcher.window_width == geometry["window_width"]
            and self._config.launcher.window_height == geometry["window_height"]
        ):
            return
        self._config.launcher = self._config.launcher.model_copy(update=geometry)
        self._config.save(self._config_path)

    def _restore_visible_geometry(self) -> None:
        if self._config is None:
            return
        screen = self._screen_for_restore()
        if screen is None:
            return
        self._last_screen_name = screen.name() or self._config.launcher.window_screen
        available = screen.availableGeometry()
        saved_width = max(self.width(), 1)
        saved_height = max(self.height(), 1)
        width = min(saved_width, available.width())
        height = min(saved_height, available.height())
        x = self._config.launcher.window_x
        y = self._config.launcher.window_y
        if x is None or y is None:
            self.setGeometry(self._centered_rect(available, width, height))
            return
        saved_rect = available.__class__(x, y, saved_width, saved_height)
        target_available = self._available_geometry_for_saved_rect(saved_rect) or available
        if saved_rect.intersects(target_available):
            self.setGeometry(x, y, min(saved_width, target_available.width()), min(saved_height, target_available.height()))
            return
        max_x = target_available.x() + max(target_available.width() - width, 0)
        max_y = target_available.y() + max(target_available.height() - height, 0)
        clamped_x = min(max(x, target_available.x()), max_x)
        clamped_y = min(max(y, target_available.y()), max_y)
        self.setGeometry(clamped_x, clamped_y, width, height)

    def _screen_for_restore(self):
        if self._config is None:
            return self.screen() or self._primary_screen()
        if self._config.launcher.window_x is None or self._config.launcher.window_y is None:
            return self._screen_at_cursor() or self.screen() or self._primary_screen()
        saved_name = self._config.launcher.window_screen
        if saved_name:
            for screen in self._screens():
                if screen.name() == saved_name:
                    return screen
        saved_rect = self.geometry().__class__(
            self._config.launcher.window_x,
            self._config.launcher.window_y,
            max(self.width(), 1),
            max(self.height(), 1),
        )
        return self._screen_for_saved_rect(saved_rect) or self.screen() or self._primary_screen()

    def _available_geometry_for_saved_rect(self, saved_rect):
        screen = self._screen_for_saved_rect(saved_rect)
        if screen is not None:
            return screen.availableGeometry()
        saved_name = self._config.launcher.window_screen if self._config is not None else None
        if saved_name:
            for candidate in self._screens():
                if candidate.name() == saved_name:
                    return candidate.availableGeometry()
        current = self._screen_for_restore()
        return current.availableGeometry() if current is not None else None

    def _screen_for_saved_rect(self, saved_rect):
        best_screen = None
        best_area = -1
        for candidate in self._screens():
            intersection = candidate.availableGeometry().intersected(saved_rect)
            area = intersection.width() * intersection.height()
            if area > best_area:
                best_area = area
                best_screen = candidate
        if best_area <= 0:
            return None
        return best_screen

    @staticmethod
    def _centered_rect(available, width: int, height: int):
        x = available.x() + max((available.width() - width) // 2, 0)
        y = available.y() + max((available.height() - height) // 2, 0)
        return available.__class__(x, y, width, height)

    def _screens(self):
        return list(QGuiApplication.screens())

    def _primary_screen(self):
        return QGuiApplication.primaryScreen()

    def _screen_at_cursor(self):
        return QGuiApplication.screenAt(QCursor.pos())

    def _current_screen_name(self) -> str | None:
        screen = self.screen()
        if screen is not None and screen.name():
            self._last_screen_name = screen.name()
            return self._last_screen_name
        derived_screen = self._screen_for_saved_rect(self.frameGeometry())
        if derived_screen is not None and derived_screen.name():
            self._last_screen_name = derived_screen.name()
        return self._last_screen_name
