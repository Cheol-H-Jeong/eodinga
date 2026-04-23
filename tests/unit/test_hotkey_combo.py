from __future__ import annotations

from eodinga.launcher.hotkey_combo import normalize_hotkey_combo


def test_normalize_hotkey_combo_canonicalizes_aliases_spacing_and_case() -> None:
    assert normalize_hotkey_combo(" Control + Alt + K ") == "ctrl+alt+k"


def test_normalize_hotkey_combo_deduplicates_modifiers_and_orders_them() -> None:
    assert normalize_hotkey_combo("shift+ctrl+alt+ctrl+space") == "ctrl+shift+alt+space"


def test_normalize_hotkey_combo_returns_empty_string_for_blank_input() -> None:
    assert normalize_hotkey_combo("   ") == ""
