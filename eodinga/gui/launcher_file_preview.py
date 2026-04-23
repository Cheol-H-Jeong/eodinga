from __future__ import annotations

from pathlib import Path

from eodinga.common import SearchHit

MAX_PREVIEW_BYTES = 16 * 1024
MAX_PREVIEW_CHARS = 400
REPLACEMENT_CHAR = "\ufffd"
_UTF16_BOMS = (
    (b"\xff\xfe", "utf-16-le"),
    (b"\xfe\xff", "utf-16-be"),
)


def filesystem_preview_snippet(hit: SearchHit) -> str | None:
    path = hit.path
    if hit.snippet or not _is_regular_file(path):
        return None
    try:
        with path.open("rb") as handle:
            raw = handle.read(MAX_PREVIEW_BYTES)
    except OSError:
        return None
    if not raw or b"\x00" in raw:
        decoded = _decode_text_preview(raw)
        return _compact_preview_text(decoded)
    decoded = _decode_text_preview(raw)
    return _compact_preview_text(decoded)


def _decode_text_preview(raw: bytes) -> str | None:
    for bom, encoding in _UTF16_BOMS:
        if raw.startswith(bom):
            return _decode_with_replacement_guard(raw[len(bom) :], encoding)
    decoded = _decode_with_replacement_guard(raw, "utf-8-sig")
    if decoded is not None:
        return decoded
    utf16_order = _utf16_candidate_order(raw)
    if utf16_order is not None:
        for encoding in utf16_order:
            decoded = _decode_with_replacement_guard(raw, encoding)
            if decoded is not None:
                return decoded
    return None


def _decode_with_replacement_guard(raw: bytes, encoding: str) -> str | None:
    try:
        text = raw.decode(encoding, errors="replace")
    except LookupError:
        return None
    if text.count(REPLACEMENT_CHAR) > max(3, len(text) // 20):
        return None
    if "\x00" in text:
        return None
    return text


def _utf16_candidate_order(raw: bytes) -> tuple[str, str] | None:
    if len(raw) < 4 or len(raw) % 2 != 0:
        return None
    even_nuls = sum(1 for index in range(0, len(raw), 2) if raw[index] == 0)
    odd_nuls = sum(1 for index in range(1, len(raw), 2) if raw[index] == 0)
    pair_count = len(raw) // 2
    threshold = max(2, pair_count // 3)
    if even_nuls < threshold and odd_nuls < threshold:
        return None
    if even_nuls > odd_nuls:
        return ("utf-16-be", "utf-16-le")
    if odd_nuls > even_nuls:
        return ("utf-16-le", "utf-16-be")
    return ("utf-16-le", "utf-16-be")


def _compact_preview_text(text: str | None) -> str | None:
    if text is None:
        return None
    compact = " ".join(text.split())
    if not compact:
        return None
    if len(compact) <= MAX_PREVIEW_CHARS:
        return compact
    return f"{compact[:MAX_PREVIEW_CHARS].rstrip()}..."


def _is_regular_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


__all__ = ["filesystem_preview_snippet"]
