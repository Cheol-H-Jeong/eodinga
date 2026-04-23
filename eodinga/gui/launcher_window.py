from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtCore import QPoint, QTimer, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtGui import QCloseEvent, QHideEvent, QMoveEvent, QResizeEvent, QShowEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizeGrip, QVBoxLayout, QWidget

from eodinga.config import AppConfig
from eodinga.gui.design import MOTION_DEBOUNCE_MS
from eodinga.gui.launcher import LauncherPanel, LauncherState, SearchFn


class _FramelessDragHandle(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Launcher drag handle")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._drag_origin: QPoint | None = None
        self._window_origin: QPoint | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Launcher", self)
        title.setProperty("role", "secondary")
        title.setAccessibleName("Launcher drag handle title")
        hint = QLabel("Drag to move", self)
        hint.setProperty("role", "secondary")
        hint.setAccessibleName("Launcher drag handle hint")
        layout.addWidget(title)
        layout.addStretch(1)
        layout.addWidget(hint)

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        window = self.window()
        self._drag_origin = event.globalPosition().toPoint()
        self._window_origin = window.pos()
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_origin is None or self._window_origin is None or not event.buttons() & Qt.MouseButton.LeftButton:
            super().mouseMoveEvent(event)
            return
        delta = event.globalPosition().toPoint() - self._drag_origin
        self.window().move(self._window_origin + delta)
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = None
            self._window_origin = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)


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
        self._drag_handle = _FramelessDragHandle(self)
        self._size_grip = QSizeGrip(self)
        self._size_grip.setAccessibleName("Launcher resize grip")
        self._install_frameless_controls()
        self._set_frameless_controls_visible(frameless)
        self.resize(width, height)

    @property
    def drag_handle(self) -> QWidget:
        return self._drag_handle

    @property
    def resize_grip(self) -> QSizeGrip:
        return self._size_grip

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
        self._set_frameless_controls_visible(enabled)

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

    def _restore_visible_geometry(self) -> None:
        if self._config is None:
            return
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        saved_width = max(self.width(), 1)
        saved_height = max(self.height(), 1)
        width = min(saved_width, available.width())
        height = min(saved_height, available.height())
        x = self._config.launcher.window_x
        y = self._config.launcher.window_y
        if x is None or y is None:
            self._center_on_available_screen(width, height, available)
            return
        saved_rect = available.__class__(x, y, saved_width, saved_height)
        if saved_rect.intersects(available):
            self.setGeometry(x, y, width, height)
            return
        max_x = available.x() + max(available.width() - width, 0)
        max_y = available.y() + max(available.height() - height, 0)
        clamped_x = min(max(x, available.x()), max_x)
        clamped_y = min(max(y, available.y()), max_y)
        self.setGeometry(clamped_x, clamped_y, width, height)

    def _center_on_available_screen(self, width: int, height: int, available) -> None:
        centered_x = available.x() + max((available.width() - width) // 2, 0)
        centered_y = available.y() + max((available.height() - height) // 2, 0)
        self.setGeometry(centered_x, centered_y, width, height)

    def _install_frameless_controls(self) -> None:
        layout = cast(QVBoxLayout, self.layout())
        layout.insertWidget(0, self._drag_handle)
        layout.addWidget(self._size_grip, 0, Qt.AlignmentFlag.AlignRight)

    def _set_frameless_controls_visible(self, enabled: bool) -> None:
        self._drag_handle.setVisible(enabled)
        self._size_grip.setVisible(enabled)
