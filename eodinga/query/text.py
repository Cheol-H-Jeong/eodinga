from __future__ import annotations

import re
import unicodedata
from typing import Literal

_SEPARATOR_PATTERN = re.compile(r"[\W_]+")


def normalize_search_text(value: str, case_sensitive: bool) -> str:
    normalized = unicodedata.normalize("NFC", value)
    return normalized if case_sensitive else normalized.casefold()


def phrase_tokens(value: str, *, case_sensitive: bool) -> tuple[str, ...]:
    normalized = normalize_search_text(value, case_sensitive=case_sensitive)
    return tuple(token for token in _SEPARATOR_PATTERN.split(normalized) if token)


def phrase_matches(value: str, phrase: str, *, case_sensitive: bool) -> bool:
    normalized_phrase = normalize_search_text(phrase, case_sensitive=case_sensitive)
    normalized_value = normalize_search_text(value, case_sensitive=case_sensitive)
    if normalized_phrase in normalized_value:
        return True
    tokens = tuple(token for token in _SEPARATOR_PATTERN.split(normalized_phrase) if token)
    if len(tokens) < 2:
        return False
    pattern = r"[\W_]+".join(re.escape(token) for token in tokens)
    return bool(re.search(pattern, normalized_value))


def fts_literal(value: str, kind: Literal["word", "phrase"]) -> str:
    if kind == "word":
        escaped = value.replace('"', '""')
        return f'"{escaped}"'
    tokens = phrase_tokens(value, case_sensitive=True)
    if len(tokens) < 2:
        escaped = value.replace('"', '""')
        return f'"{escaped}"'
    return " ".join(f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens)
