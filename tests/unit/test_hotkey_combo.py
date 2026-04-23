from __future__ import annotations

from types import ModuleType

import pytest

from eodinga.launcher.hotkey_combo import normalize_hotkey_combo
from eodinga.launcher.hotkey_linux import _parse_x_combo, _pynput_combo
from eodinga.launcher.hotkey_win import MOD_ALT, MOD_CONTROL, _parse_combo


def test_normalize_hotkey_combo_canonicalizes_aliases_and_order() -> None:
    assert normalize_hotkey_combo(" Shift + Control + Return ") == "ctrl+shift+enter"
    assert normalize_hotkey_combo("option+cmd+PgDn") == "alt+win+pagedown"


def test_normalize_hotkey_combo_rejects_invalid_shapes() -> None:
    with pytest.raises(ValueError, match="missing key"):
        normalize_hotkey_combo("ctrl+shift")
    with pytest.raises(ValueError, match="duplicate hotkey modifier"):
        normalize_hotkey_combo("ctrl+control+a")
    with pytest.raises(ValueError, match="exactly one key"):
        normalize_hotkey_combo("ctrl+a+b")


def test_windows_hotkey_parser_accepts_named_and_function_keys() -> None:
    modifiers, key_code = _parse_combo("Alt+F4")

    assert modifiers == MOD_ALT
    assert key_code == 0x73

    modifiers, key_code = _parse_combo("Ctrl+Home")

    assert modifiers == MOD_CONTROL
    assert key_code == 0x24


def test_pynput_combo_uses_backend_key_names() -> None:
    assert _pynput_combo("Ctrl+Shift+PageDown") == "<ctrl>+<shift>+<page_down>"
    assert _pynput_combo("Alt+Space") == "<alt>+<space>"


def test_xlib_hotkey_parser_maps_named_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    requested: list[int] = []
    xk_module = ModuleType("Xlib.XK")
    setattr(xk_module, "XK_Page_Up", 0xFF55)
    x_module = ModuleType("Xlib.X")
    setattr(x_module, "ControlMask", 0x04)

    class _DisplayStub:
        def keysym_to_keycode(self, keysym: int) -> int:
            requested.append(keysym)
            return 42

    monkeypatch.setattr(
        "eodinga.launcher.hotkey_linux.import_module",
        lambda module_name: xk_module if module_name == "Xlib.XK" else x_module,
    )

    modifiers, key_code = _parse_x_combo(_DisplayStub(), "Ctrl+PageUp")

    assert modifiers == 0x04
    assert key_code == 42
    assert requested == [0xFF55]
