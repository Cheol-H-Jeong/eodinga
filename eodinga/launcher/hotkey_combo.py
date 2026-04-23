from __future__ import annotations

MODIFIER_ALIASES = {
    "control": "ctrl",
    "ctrl": "ctrl",
    "shift": "shift",
    "alt": "alt",
    "option": "alt",
    "win": "win",
    "cmd": "win",
    "command": "win",
    "meta": "win",
    "super": "win",
}

KEY_ALIASES = {
    " ": "space",
    "del": "delete",
    "esc": "escape",
    "pgdn": "pagedown",
    "pgdown": "pagedown",
    "pgup": "pageup",
    "return": "enter",
}

MODIFIER_ORDER = ("ctrl", "shift", "alt", "win")
NAMED_KEYS = {
    "backspace",
    "delete",
    "down",
    "end",
    "enter",
    "escape",
    "home",
    "left",
    "pagedown",
    "pageup",
    "right",
    "space",
    "tab",
    "up",
}
FUNCTION_KEYS = {f"f{index}" for index in range(1, 13)}


def normalize_hotkey_combo(combo: str) -> str:
    normalized = combo.strip().lower()
    if not normalized:
        return ""

    raw_parts = [part.strip() for part in normalized.split("+")]
    if any(not part for part in raw_parts):
        raise ValueError(f"invalid hotkey combo: {combo}")

    modifiers: set[str] = set()
    key_name = ""
    for part in raw_parts:
        modifier = MODIFIER_ALIASES.get(part)
        if modifier is not None:
            if modifier in modifiers:
                raise ValueError(f"duplicate hotkey modifier: {part}")
            modifiers.add(modifier)
            continue
        if key_name:
            raise ValueError(f"hotkey combo must contain exactly one key: {combo}")
        key_name = _normalize_key_name(part)

    if not key_name:
        raise ValueError(f"hotkey combo missing key: {combo}")
    ordered_modifiers = [modifier for modifier in MODIFIER_ORDER if modifier in modifiers]
    return "+".join([*ordered_modifiers, key_name])


def _normalize_key_name(part: str) -> str:
    key_name = KEY_ALIASES.get(part, part)
    if len(key_name) == 1 and key_name.isprintable() and key_name != "+":
        return key_name
    if key_name in NAMED_KEYS or key_name in FUNCTION_KEYS:
        return key_name
    raise ValueError(f"unsupported hotkey key: {part}")


__all__ = ["normalize_hotkey_combo"]
