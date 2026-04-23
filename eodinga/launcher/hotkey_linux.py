from __future__ import annotations

import os
from collections.abc import Callable
from importlib import import_module
from threading import Event, Thread
from time import sleep

from eodinga.launcher.hotkey_combo import normalize_hotkey_combo
from eodinga.observability import get_logger

HotkeyCallback = Callable[[], None]


def _require_linux() -> None:
    import sys

    if not sys.platform.startswith("linux"):
        raise RuntimeError("Linux hotkey backend is only available on Linux")


class _BackendBase:
    def register(self, combo: str, callback: HotkeyCallback) -> None:
        raise NotImplementedError

    def unregister(self) -> None:
        raise NotImplementedError

    def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError


class _PynputBackend(_BackendBase):
    def __init__(self) -> None:
        keyboard_module = import_module("pynput.keyboard")
        self._listener_cls = getattr(keyboard_module, "GlobalHotKeys")
        self._combo = ""
        self._callback: HotkeyCallback | None = None
        self._listener = None

    def register(self, combo: str, callback: HotkeyCallback) -> None:
        self._combo = combo
        self._callback = callback
        if self._listener is not None:
            self.start()

    def unregister(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        self._combo = ""
        self._callback = None

    def start(self) -> None:
        if not self._combo or self._callback is None:
            return
        if self._listener is not None:
            self._listener.stop()
        normalized = _pynput_combo(self._combo)
        self._listener = self._listener_cls({normalized: self._callback})
        self._listener.start()

    def stop(self) -> None:
        self.unregister()


class _XlibBackend(_BackendBase):
    def __init__(self) -> None:
        x_display_module = import_module("Xlib.display")
        x_module = import_module("Xlib.X")
        self._display_cls = getattr(x_display_module, "Display")
        self._x_module = x_module
        self._display = None
        self._combo = ""
        self._callback: HotkeyCallback | None = None
        self._thread: Thread | None = None
        self._running = Event()

    def register(self, combo: str, callback: HotkeyCallback) -> None:
        self._combo = combo
        self._callback = callback

    def unregister(self) -> None:
        self._combo = ""
        self._callback = None

    def start(self) -> None:
        if not self._combo or self._callback is None:
            return
        if self._thread and self._thread.is_alive():
            return
        self._running.set()
        self._thread = Thread(target=self._loop, daemon=True, name="eodinga-hotkey-xlib")
        self._thread.start()

    def stop(self) -> None:
        self._running.clear()
        if self._thread is not None:
            self._thread.join(timeout=0.5)
        if self._display is not None:
            self._display.close()
            self._display = None

    def _loop(self) -> None:
        self._display = self._display_cls()
        root = self._display.screen().root
        modifiers, keycode = _parse_x_combo(self._display, self._combo)
        root.grab_key(keycode, modifiers, True, self._x_module.GrabModeAsync, self._x_module.GrabModeAsync)
        self._display.sync()
        while self._running.is_set():
            while self._display.pending_events():
                event = self._display.next_event()
                if event.type == self._x_module.KeyPress and self._callback is not None:
                    self._callback()
            sleep(0.01)
        get_logger().debug("stopped Xlib hotkey loop")


def _parse_x_combo(display, combo: str) -> tuple[int, int]:
    xk_module = import_module("Xlib.XK")
    x_module = import_module("Xlib.X")
    key_name = ""
    modifiers = 0
    for part in normalize_hotkey_combo(combo).split("+"):
        if part == "ctrl":
            modifiers |= x_module.ControlMask
        elif part == "shift":
            modifiers |= x_module.ShiftMask
        elif part == "alt":
            modifiers |= x_module.Mod1Mask
        elif part == "win":
            modifiers |= x_module.Mod4Mask
        else:
            key_name = part
    if not key_name:
        raise ValueError(f"hotkey combo missing key: {combo}")
    keysym = getattr(xk_module, f"XK_{_x_keysym_name(key_name)}", None)
    if keysym is None:
        if len(key_name) != 1:
            raise ValueError(f"unsupported hotkey key: {key_name}")
        keysym = ord(key_name)
    return modifiers, display.keysym_to_keycode(keysym)


def _pynput_combo(combo: str) -> str:
    parts = []
    for part in normalize_hotkey_combo(combo).split("+"):
        if part in {"ctrl", "shift", "alt", "win"}:
            parts.append(f"<{part}>")
            continue
        parts.append(f"<{_pynput_key_name(part)}>") if len(part) > 1 else parts.append(part)
    return "+".join(parts)


def _pynput_key_name(key_name: str) -> str:
    return {
        "delete": "delete",
        "down": "down",
        "end": "end",
        "enter": "enter",
        "escape": "esc",
        "home": "home",
        "left": "left",
        "pagedown": "page_down",
        "pageup": "page_up",
        "right": "right",
        "space": "space",
        "tab": "tab",
        "up": "up",
        "backspace": "backspace",
    }.get(key_name, key_name)


def _x_keysym_name(key_name: str) -> str:
    return {
        "backspace": "BackSpace",
        "delete": "Delete",
        "down": "Down",
        "end": "End",
        "enter": "Return",
        "escape": "Escape",
        "home": "Home",
        "left": "Left",
        "pagedown": "Page_Down",
        "pageup": "Page_Up",
        "right": "Right",
        "space": "space",
        "tab": "Tab",
        "up": "Up",
    }.get(key_name, key_name.upper() if key_name.startswith("f") else key_name)


class PlatformHotkeyService:
    def __init__(self) -> None:
        _require_linux()
        self._backend = self._make_backend()

    def register(self, combo: str, callback: HotkeyCallback) -> None:
        self._backend.register(combo, callback)

    def unregister(self) -> None:
        self._backend.unregister()

    def start(self) -> None:
        self._backend.start()

    def stop(self) -> None:
        self._backend.stop()

    def _make_backend(self) -> _BackendBase:
        if os.environ.get("DISPLAY"):
            try:
                return _XlibBackend()
            except ModuleNotFoundError:
                get_logger().warning("python-xlib unavailable, falling back to pynput")
        return _PynputBackend()
