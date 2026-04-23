from __future__ import annotations

import re
import unicodedata
from typing import Literal


_WHITESPACE_RE = re.compile(r"\s+")


def make_regex_flags(flag_text: str) -> int:
    flags = 0
    for flag in flag_text.lower():
        if flag == "i":
            flags |= re.IGNORECASE
        if flag == "m":
            flags |= re.MULTILINE
        if flag == "s":
            flags |= re.DOTALL
    return flags


def normalize_search_text(value: str, case_sensitive: bool) -> str:
    normalized = unicodedata.normalize("NFC", value)
    return normalized if case_sensitive else normalized.casefold()


def text_matches(
    value: str,
    needle: str,
    case_sensitive: bool,
    *,
    kind: Literal["word", "phrase"] = "word",
) -> bool:
    haystack = normalize_search_text(value, case_sensitive=case_sensitive)
    normalized_needle = normalize_search_text(needle, case_sensitive=case_sensitive)
    if kind == "phrase":
        haystack = _WHITESPACE_RE.sub(" ", haystack)
        normalized_needle = _WHITESPACE_RE.sub(" ", normalized_needle)
    return normalized_needle in haystack


def regex_matches(
    text: str,
    pattern: str,
    flags: str,
    *,
    negated: bool,
    default_case_sensitive: bool,
) -> bool:
    compiled = re.compile(
        pattern,
        make_regex_flags(flags)
        | (0 if default_case_sensitive or "i" in flags.lower() else re.IGNORECASE),
    )
    matched = bool(compiled.search(text))
    return not matched if negated else matched
