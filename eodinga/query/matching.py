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


def text_startswith(
    value: str,
    needle: str,
    case_sensitive: bool,
    *,
    kind: MatchKind = "word",
) -> bool:
    haystack = normalize_search_text(value, case_sensitive=case_sensitive)
    normalized_needle = normalize_search_text(needle, case_sensitive=case_sensitive)
    if kind == "phrase":
        return phrase_startswith(haystack, normalized_needle)
    return haystack.startswith(normalized_needle)


def phrase_matches(value: str, phrase: str) -> bool:
    if phrase in value:
        return True
    pattern = _phrase_pattern(phrase)
    return bool(pattern and re.search(pattern, value, re.UNICODE))


def phrase_startswith(value: str, phrase: str) -> bool:
    if value.startswith(phrase):
        return True
    pattern = _phrase_pattern(phrase, anchored=True)
    return bool(pattern and re.search(pattern, value, re.UNICODE))


def _phrase_pattern(phrase: str, *, anchored: bool = False) -> str:
    tokens = [token for token in _PHRASE_SEPARATOR_RE.split(phrase) if token]
    if not tokens:
        return ""
    prefix = "^" if anchored else ""
    return prefix + r"[\W_]+".join(re.escape(token) for token in tokens)
