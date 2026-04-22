from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from types import ModuleType

from eodinga.observability import get_logger

HotkeyCallback = Callable[[], None]


def _module_name_for_platform(platform_name: str) -> str:
    if platform_name.startswith("win"):
        return "eodinga.launcher.hotkey_win"
    if platform_name.startswith("linux"):
        return "eodinga.launcher.hotkey_linux"
    raise RuntimeError(f"unsupported hotkey platform: {platform_name}")


def _load_backend_module(platform_name: str | None = None) -> ModuleType:
    import sys

    resolved_platform = platform_name or sys.platform
    module_name = _module_name_for_platform(resolved_platform)
    return import_module(module_name)


class HotkeyService:
    def __init__(self, platform_name: str | None = None) -> None:
        module = _load_backend_module(platform_name)
        backend_cls = getattr(module, "PlatformHotkeyService")
        self._backend = backend_cls()
        get_logger().debug("loaded hotkey backend {}", backend_cls.__name__)

    def register(self, combo: str, callback: HotkeyCallback) -> None:
        self._backend.register(combo, callback)

    def unregister(self) -> None:
        self._backend.unregister()

    def start(self) -> None:
        self._backend.start()

    def stop(self) -> None:
        self._backend.stop()

