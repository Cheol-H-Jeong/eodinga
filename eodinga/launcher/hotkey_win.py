from __future__ import annotations

import ctypes
import threading
from collections.abc import Callable
from ctypes import wintypes
from time import sleep
from typing import Any, cast

from eodinga.observability import get_logger

HotkeyCallback = Callable[[], None]

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
PM_REMOVE = 0x0001
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

_VK_MAP = {
    "space": 0x20,
    "enter": 0x0D,
}


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt_x", ctypes.c_long),
        ("pt_y", ctypes.c_long),
    ]


def _ensure_windows() -> None:
    import sys

    if not sys.platform.startswith("win"):
        raise RuntimeError("Windows hotkey backend is only available on Windows")


def _windll() -> Any:
    return cast(Any, getattr(ctypes, "windll"))


def _parse_combo(combo: str) -> tuple[int, int]:
    parts = [part.strip().lower() for part in combo.split("+") if part.strip()]
    modifiers = 0
    key_name = ""
    for part in parts:
        if part == "ctrl":
            modifiers |= MOD_CONTROL
        elif part == "shift":
            modifiers |= MOD_SHIFT
        elif part == "alt":
            modifiers |= MOD_ALT
        elif part == "win":
            modifiers |= MOD_WIN
        else:
            key_name = part
    if not key_name:
        raise ValueError(f"hotkey combo missing key: {combo}")
    virtual_key = _VK_MAP.get(key_name, ord(key_name.upper()) if len(key_name) == 1 else 0)
    if virtual_key == 0:
        raise ValueError(f"unsupported hotkey key: {key_name}")
    return modifiers, virtual_key


class PlatformHotkeyService:
    def __init__(self) -> None:
        _ensure_windows()
        self._combo = ""
        self._callback: HotkeyCallback | None = None
        self._thread: threading.Thread | None = None
        self._running = threading.Event()
        self._ready = threading.Event()
        self._thread_id = 0
        self._hotkey_id = 1

    def register(self, combo: str, callback: HotkeyCallback) -> None:
        self._combo = combo
        self._callback = callback
        if self._running.is_set():
            self._register_hotkey()

    def unregister(self) -> None:
        if self._running.is_set():
            _windll().user32.UnregisterHotKey(None, self._hotkey_id)
        self._combo = ""
        self._callback = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._running.set()
        self._thread = threading.Thread(target=self._message_loop, daemon=True, name="eodinga-hotkey-win")
        self._thread.start()
        self._ready.wait(timeout=1.0)

    def stop(self) -> None:
        self._running.clear()
        if self._thread_id:
            _windll().user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread:
            self._thread.join(timeout=1.0)
        self.unregister()

    def _register_hotkey(self) -> None:
        if not self._combo:
            return
        modifiers, virtual_key = _parse_combo(self._combo)
        _windll().user32.UnregisterHotKey(None, self._hotkey_id)
        ok = _windll().user32.RegisterHotKey(None, self._hotkey_id, modifiers, virtual_key)
        if ok == 0:
            raise RuntimeError(f"failed to register hotkey: {self._combo}")

    def _message_loop(self) -> None:
        msg = MSG()
        self._thread_id = _windll().kernel32.GetCurrentThreadId()
        self._register_hotkey()
        self._ready.set()
        while self._running.is_set():
            has_message = _windll().user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE)
            if has_message:
                if msg.message == WM_HOTKEY and self._callback is not None:
                    self._callback()
                if msg.message == WM_QUIT:
                    break
            else:
                sleep(0.01)
        _windll().user32.UnregisterHotKey(None, self._hotkey_id)
        get_logger().debug("stopped Windows hotkey loop")
