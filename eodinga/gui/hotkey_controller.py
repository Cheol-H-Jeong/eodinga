from __future__ import annotations

from typing import Protocol

from PySide6.QtCore import QObject, Signal

from eodinga.gui.launcher_window import LauncherWindow
from eodinga.launcher.hotkey import HotkeyService
from eodinga.observability import get_logger

_MODIFIER_ALIASES = {
    "ctrl": "ctrl",
    "control": "ctrl",
    "alt": "alt",
    "option": "alt",
    "shift": "shift",
    "win": "win",
    "meta": "win",
    "super": "win",
    "cmd": "win",
    "command": "win",
}
_MODIFIER_ORDER = ("ctrl", "alt", "shift", "win")


class HotkeyServiceLike(Protocol):
    def register(self, combo: str, callback) -> None: ...

    def unregister(self) -> None: ...

    def start(self) -> None: ...

    def stop(self) -> None: ...


class LauncherHotkeyController(QObject):
    toggle_requested = Signal()

    def __init__(
        self,
        launcher_window: LauncherWindow,
        combo: str,
        hotkey_service: HotkeyServiceLike | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._launcher_window = launcher_window
        self._service = hotkey_service if hotkey_service is not None else self._build_service()
        self._combo = normalize_hotkey_combo(combo)
        self.toggle_requested.connect(self.toggle_launcher)
        if self._service is not None and self._combo:
            self._apply_combo(self._combo)

    @property
    def combo(self) -> str:
        return self._combo

    @property
    def available(self) -> bool:
        return self._service is not None

    def rebind(self, combo: str) -> None:
        normalized = normalize_hotkey_combo(combo)
        if not normalized or normalized == self._combo:
            return
        previous = self._combo
        if self._service is None:
            self._combo = normalized
            return
        try:
            self._apply_combo(normalized)
        except Exception:
            self._apply_combo(previous)
            raise

    def stop(self) -> None:
        if self._service is None:
            return
        self._service.stop()

    def toggle_launcher(self) -> None:
        if self._launcher_window.isVisible():
            self._launcher_window.hide()
            return
        self._launcher_window.show()
        self._launcher_window.raise_()
        self._launcher_window.activateWindow()
        self._launcher_window.query_field.setFocus()
        self._launcher_window.query_field.selectAll()

    def _build_service(self) -> HotkeyServiceLike | None:
        try:
            return HotkeyService()
        except Exception as error:
            get_logger().warning("launcher hotkey backend unavailable: {}", error)
            return None

    def _apply_combo(self, combo: str) -> None:
        assert self._service is not None
        self._service.stop()
        self._service.unregister()
        self._service.register(combo, self.toggle_requested.emit)
        self._service.start()
        self._combo = combo
        get_logger().debug("launcher hotkey bound to {}", combo)


def normalize_hotkey_combo(combo: str) -> str:
    parts = [part.strip().lower() for part in combo.split("+") if part.strip()]
    if not parts:
        return ""
    modifiers: list[str] = []
    key_parts: list[str] = []
    for part in parts:
        modifier = _MODIFIER_ALIASES.get(part)
        if modifier is not None:
            if modifier not in modifiers:
                modifiers.append(modifier)
            continue
        key_parts.append(part)
    if not key_parts:
        return "+".join(modifier for modifier in _MODIFIER_ORDER if modifier in modifiers)
    key = key_parts[-1]
    ordered_modifiers = [modifier for modifier in _MODIFIER_ORDER if modifier in modifiers]
    return "+".join([*ordered_modifiers, key])
