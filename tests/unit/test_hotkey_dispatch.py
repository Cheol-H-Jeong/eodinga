from __future__ import annotations

from types import ModuleType

import pytest

from eodinga.launcher.hotkey import HotkeyService, _module_name_for_platform


def test_module_name_for_platform() -> None:
    assert _module_name_for_platform("win32") == "eodinga.launcher.hotkey_win"
    assert _module_name_for_platform("linux") == "eodinga.launcher.hotkey_linux"


def test_hotkey_service_picks_windows_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    selected: list[str] = []

    class StubBackend:
        def __init__(self) -> None:
            selected.append("win")

        def register(self, combo: str, callback) -> None:
            return None

        def unregister(self) -> None:
            return None

        def start(self) -> None:
            return None

        def stop(self) -> None:
            return None

    stub_module = ModuleType("stub_hotkey_win")
    setattr(stub_module, "PlatformHotkeyService", StubBackend)
    monkeypatch.setattr("eodinga.launcher.hotkey.import_module", lambda module_name: stub_module)

    HotkeyService(platform_name="win32")

    assert selected == ["win"]


def test_hotkey_service_picks_linux_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    selected: list[str] = []

    class StubBackend:
        def __init__(self) -> None:
            selected.append("linux")

        def register(self, combo: str, callback) -> None:
            return None

        def unregister(self) -> None:
            return None

        def start(self) -> None:
            return None

        def stop(self) -> None:
            return None

    stub_module = ModuleType("stub_hotkey_linux")
    setattr(stub_module, "PlatformHotkeyService", StubBackend)
    monkeypatch.setattr("eodinga.launcher.hotkey.import_module", lambda module_name: stub_module)

    HotkeyService(platform_name="linux")

    assert selected == ["linux"]


def test_hotkey_service_raises_for_unsupported_platform() -> None:
    with pytest.raises(RuntimeError):
        HotkeyService(platform_name="darwin")

