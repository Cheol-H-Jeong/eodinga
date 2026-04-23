from __future__ import annotations

from types import ModuleType

import pytest
from PySide6.QtWidgets import QApplication

from eodinga.config import AppConfig, load
from eodinga.gui.app import EodingaWindow
from eodinga.gui.hotkey_controller import normalize_hotkey_combo
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


class _HotkeyServiceSpy:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.callback = None

    def register(self, combo: str, callback) -> None:
        self.calls.append(("register", combo))
        self.callback = callback

    def unregister(self) -> None:
        self.calls.append(("unregister", ""))
        self.callback = None

    def start(self) -> None:
        self.calls.append(("start", ""))

    def stop(self) -> None:
        self.calls.append(("stop", ""))


def test_normalize_hotkey_combo_canonicalizes_aliases_and_spacing() -> None:
    assert normalize_hotkey_combo(" Control + Alt + K ") == "ctrl+alt+k"
    assert normalize_hotkey_combo(" Command + Shift + Space ") == "shift+win+space"


def test_settings_tab_rebinds_hotkey_without_restart(
    monkeypatch: pytest.MonkeyPatch,
    qapp: QApplication,
    temp_config_path,
) -> None:
    hotkey_service = _HotkeyServiceSpy()
    config = AppConfig()
    window = EodingaWindow(config=config, config_path=temp_config_path, hotkey_service=hotkey_service)
    monkeypatch.setattr(
        "eodinga.gui.tabs.settings.QInputDialog.getText",
        lambda *args, **kwargs: (" Control + Alt + K ", True),
    )

    window.settings_tab.remap_hotkey_button.click()
    qapp.processEvents()

    assert hotkey_service.calls[-4:] == [
        ("stop", ""),
        ("unregister", ""),
        ("register", "ctrl+alt+k"),
        ("start", ""),
    ]
    assert window.settings_tab.hotkey_label.text() == "Launcher hotkey: ctrl+alt+k"
    assert load(temp_config_path).launcher.hotkey == "ctrl+alt+k"
