from __future__ import annotations

import unicodedata


def normalize_search_text(value: str, case_sensitive: bool) -> str:
    normalized = unicodedata.normalize("NFC", value)
    return normalized if case_sensitive else normalized.casefold()


def phrase_matches(value: str, phrase: str, case_sensitive: bool) -> bool:
    normalized_value = normalize_search_text(value, case_sensitive=case_sensitive)
    normalized_phrase = normalize_search_text(phrase, case_sensitive=case_sensitive)
    if normalized_phrase in normalized_value:
        return True
    folded_value = _fold_phrase_boundaries(normalized_value)
    folded_phrase = _fold_phrase_boundaries(normalized_phrase)
    if not folded_phrase:
        return False
    return folded_phrase in folded_value


def text_matches(
    value: str,
    needle: str,
    case_sensitive: bool,
    *,
    kind: str = "word",
) -> bool:
    if kind == "phrase":
        return phrase_matches(value, needle, case_sensitive)
    normalized_value = normalize_search_text(value, case_sensitive=case_sensitive)
    normalized_needle = normalize_search_text(needle, case_sensitive=case_sensitive)
    return normalized_needle in normalized_value


def _fold_phrase_boundaries(value: str) -> str:
    parts: list[str] = []
    in_gap = False
    for char in value:
        if char.isalnum():
            parts.append(char)
            in_gap = False
            continue
        if not in_gap and parts:
            parts.append(" ")
        in_gap = True
    return "".join(parts).strip()
