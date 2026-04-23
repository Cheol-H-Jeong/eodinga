from __future__ import annotations

from pathlib import Path
from typing import cast

from eodinga.common import SearchHit
from eodinga.core.fs import open_readonly

MAX_PREVIEW_BYTES = 16 * 1024
MAX_PREVIEW_CHARS = 400
REPLACEMENT_CHAR = "\ufffd"


def filesystem_preview_snippet(hit: SearchHit) -> str | None:
    path = hit.path
    if hit.snippet or not _is_regular_file(path):
        return None
    try:
        with open_readonly(path, mode="rb") as handle:
            raw = cast(bytes, handle.read(MAX_PREVIEW_BYTES))
    except OSError:
        return None
    if not raw or b"\x00" in raw:
        return None
    text = raw.decode("utf-8", errors="replace")
    if text.count(REPLACEMENT_CHAR) > max(3, len(text) // 20):
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
