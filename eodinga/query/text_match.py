from __future__ import annotations

import re
import unicodedata
from typing import Literal

_SEPARATOR_PATTERN = re.compile(r"[\W_]+", re.UNICODE)


def normalize_search_text(value: str, case_sensitive: bool) -> str:
    normalized = unicodedata.normalize("NFC", value)
    return normalized if case_sensitive else normalized.casefold()


def text_matches(
    value: str,
    needle: str,
    *,
    case_sensitive: bool,
    kind: Literal["word", "phrase"] = "word",
) -> bool:
    haystack = normalize_search_text(value, case_sensitive=case_sensitive)
    normalized_needle = normalize_search_text(needle, case_sensitive=case_sensitive)
    if normalized_needle in haystack:
        return True
    if kind != "phrase":
        return False
    normalized_haystack = _SEPARATOR_PATTERN.sub(" ", haystack).strip()
    normalized_phrase = _SEPARATOR_PATTERN.sub(" ", normalized_needle).strip()
    if not normalized_phrase:
        return False
    return normalized_phrase in normalized_haystack


__all__ = ["normalize_search_text", "text_matches"]
