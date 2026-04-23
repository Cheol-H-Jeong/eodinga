from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from stat import S_ISDIR, S_ISREG

from eodinga.common import SearchHit

MAX_PREVIEW_BYTES = 16 * 1024
MAX_PREVIEW_CHARS = 400
REPLACEMENT_CHAR = "\ufffd"


@dataclass(frozen=True)
class FilesystemPreview:
    snippet: str | None
    metadata: str | None


def filesystem_preview(hit: SearchHit) -> FilesystemPreview | None:
    snippet = filesystem_preview_snippet(hit)
    metadata = filesystem_preview_metadata(hit.path)
    if snippet is None and metadata is None:
        return None
    return FilesystemPreview(snippet=snippet, metadata=metadata)


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


def filesystem_preview_metadata(path: Path) -> str | None:
    try:
        stat_result = path.lstat()
    except OSError:
        return None
    parts = [_path_kind(path, stat_result.st_mode)]
    if S_ISREG(stat_result.st_mode):
        parts.append(_format_size(stat_result.st_size))
    parts.append(f"modified {datetime.fromtimestamp(stat_result.st_mtime):%Y-%m-%d %H:%M}")
    return " · ".join(parts)


def _is_regular_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def _path_kind(path: Path, mode: int) -> str:
    if path.is_symlink():
        return "Symbolic link"
    if S_ISDIR(mode):
        return "Directory"
    if S_ISREG(mode):
        return "File"
    return "Filesystem entry"


def _format_size(size: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    raise AssertionError("size formatter exhausted all units")


__all__ = ["FilesystemPreview", "filesystem_preview", "filesystem_preview_metadata", "filesystem_preview_snippet"]
