from __future__ import annotations

from eodinga.launcher.hotkey_combo import is_bindable_hotkey_combo, normalize_hotkey_combo


def test_normalize_hotkey_combo_canonicalizes_aliases_spacing_and_case() -> None:
    assert normalize_hotkey_combo(" Control + Alt + K ") == "ctrl+alt+k"


def test_normalize_hotkey_combo_deduplicates_modifiers_and_orders_them() -> None:
    assert normalize_hotkey_combo("shift+ctrl+alt+ctrl+space") == "ctrl+shift+alt+space"


def test_normalize_hotkey_combo_returns_empty_string_for_blank_input() -> None:
    assert normalize_hotkey_combo("   ") == ""


def test_is_bindable_hotkey_combo_accepts_single_primary_key() -> None:
    assert is_bindable_hotkey_combo("ctrl+alt+k")
    assert is_bindable_hotkey_combo("f8")


def test_is_bindable_hotkey_combo_rejects_modifier_only_and_multi_key_combos() -> None:
    assert not is_bindable_hotkey_combo("ctrl+shift")
    assert not is_bindable_hotkey_combo("ctrl+k+l")
