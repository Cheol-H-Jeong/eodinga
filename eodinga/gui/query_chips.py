from __future__ import annotations

from html import escape
import re

_CHIP_PATTERN = re.compile(r"(?<!\S)(ext|date|size|content|path|is|root|case|regex):([^\s)]+)")
_MAX_INLINE_CHIPS = 3


def extract_query_chips(query: str) -> list[str]:
    seen: set[str] = set()
    chips: list[str] = []
    for name, value in _CHIP_PATTERN.findall(query):
        chip = f"{name}:{value}"
        lowered = chip.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        chips.append(chip)
    return chips


def render_query_chips_html(chips: list[str]) -> str:
    visible = chips[:_MAX_INLINE_CHIPS]
    parts = [
        (
            "<span style='display:inline-block; margin-left:4px; padding:1px 8px; border-radius:999px; "
            "background:#E8F0E8; color:#284B2F; font-size:10px; font-weight:600'>"
            f"{escape(chip)}"
            "</span>"
        )
        for chip in visible
    ]
    hidden = len(chips) - len(visible)
    if hidden > 0:
        parts.append(
            "<span style='display:inline-block; margin-left:4px; padding:1px 8px; border-radius:999px; "
            "background:#F1F5F9; color:#475569; font-size:10px; font-weight:600'>"
            f"+{hidden}"
            "</span>"
        )
    return "".join(parts)
