from __future__ import annotations

import re
import unicodedata
from typing import Literal

MatchKind = Literal["word", "phrase"]

_PHRASE_SEPARATOR_RE = re.compile(r"[\W_]+", re.UNICODE)


def normalize_search_text(value: str, case_sensitive: bool) -> str:
    normalized = unicodedata.normalize("NFC", value)
    return normalized if case_sensitive else normalized.casefold()


def text_matches(
    value: str,
    needle: str,
    case_sensitive: bool,
    *,
    kind: MatchKind = "word",
) -> bool:
    haystack = normalize_search_text(value, case_sensitive=case_sensitive)
    normalized_needle = normalize_search_text(needle, case_sensitive=case_sensitive)
    if kind == "phrase":
        return phrase_matches(haystack, normalized_needle)
    return normalized_needle in haystack


def phrase_matches(value: str, phrase: str) -> bool:
    if phrase in value:
        return True
    tokens = [token for token in _PHRASE_SEPARATOR_RE.split(phrase) if token]
    if not tokens:
        return False
    pattern = r"[\W_]+".join(re.escape(token) for token in tokens)
    return bool(re.search(pattern, value, re.UNICODE))
