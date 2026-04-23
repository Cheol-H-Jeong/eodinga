from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QPushButton


class PrimaryButton(QPushButton):
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        self.setProperty("variant", "primary")
        self.setAccessibleName(text)


class SecondaryButton(QPushButton):
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        self.setProperty("variant", "secondary")
        self.setAccessibleName(text)
        self._navigation_handlers: dict[int, Callable[[], None]] = {}

    def set_navigation_handler(self, key: int, handler: Callable[[], None] | None) -> None:
        if handler is None:
            self._navigation_handlers.pop(key, None)
            return
        self._navigation_handlers[key] = handler

    def clear_navigation_handlers(self) -> None:
        self._navigation_handlers.clear()

    def focusNextPrevChild(self, next: bool) -> bool:
        key = Qt.Key.Key_Tab if next else Qt.Key.Key_Backtab
        handler = self._navigation_handlers.get(key)
        if handler is not None:
            handler()
            return True
        return super().focusNextPrevChild(next)

    def event(self, event) -> bool:
        if event.type() in {QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress}:
            handler = self._navigation_handlers.get(event.key())
            if handler is not None:
                handler()
                event.accept()
                return True
        return super().event(event)
