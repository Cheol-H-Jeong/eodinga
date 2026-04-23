from __future__ import annotations

_MODIFIER_ALIASES = {
    "control": "ctrl",
    "ctrl": "ctrl",
    "shift": "shift",
    "alt": "alt",
    "option": "alt",
    "win": "win",
    "super": "win",
    "meta": "win",
    "command": "win",
    "cmd": "win",
}
_MODIFIER_ORDER = ("ctrl", "shift", "alt", "win")


def normalize_hotkey_combo(combo: str) -> str:
    parts = [part.strip().lower() for part in combo.split("+") if part.strip()]
    if not parts:
        return ""
    modifiers: list[str] = []
    modifier_set: set[str] = set()
    keys: list[str] = []
    for part in parts:
        modifier = _MODIFIER_ALIASES.get(part)
        if modifier is not None:
            if modifier not in modifier_set:
                modifier_set.add(modifier)
                modifiers.append(modifier)
            continue
        keys.append(part)
    ordered_modifiers = [modifier for modifier in _MODIFIER_ORDER if modifier in modifier_set]
    if not keys:
        return "+".join(ordered_modifiers)
    if len(keys) == 1:
        return "+".join([*ordered_modifiers, keys[0]])
    return "+".join([*ordered_modifiers, *keys])


def validate_hotkey_combo(combo: str) -> str:
    normalized = normalize_hotkey_combo(combo)
    if not normalized:
        raise ValueError("hotkey combo cannot be blank")
    parts = normalized.split("+")
    keys = [part for part in parts if part not in _MODIFIER_ALIASES.values()]
    if len(keys) != 1:
        raise ValueError(f"hotkey combo must include exactly one non-modifier key: {normalized}")
    return normalized


__all__ = ["normalize_hotkey_combo", "validate_hotkey_combo"]
