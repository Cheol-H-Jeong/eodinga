from __future__ import annotations

import os
import re
from collections.abc import Iterator
from pathlib import Path
from typing import IO, NamedTuple, cast

DENYLIST = (
    "/proc",
    "/sys",
    "/dev",
    "/snap",
    "/run",
    "/var/cache",
    "/var/lib",
    "/tmp",
    "~/.cache",
    "~/.local/share/Trash",
    "~/snap",
    "%SystemRoot%",
    "C:/$Recycle.Bin",
    "~/AppData/Local/Temp",
)

_HIDDEN_NAMES = {".git", ".hg", ".svn", ".cache", "__pycache__"}
_WINDOWS_ABS_RE = re.compile(r"^[A-Za-z]:[\\/]")


class ScandirEntry(NamedTuple):
    path: Path
    stat_result: os.stat_result | None


def open_readonly(path: Path, mode: str = "rb", encoding: str | None = None) -> IO[str] | IO[bytes]:
    if any(flag in mode for flag in ("w", "a", "+", "x")):
        raise ValueError("open_readonly only supports read modes")
    return path.open(mode=mode, encoding=encoding)


def read_bytes(path: Path) -> bytes:
    with open_readonly(path, mode="rb") as handle:
        return cast(bytes, handle.read())


def file_size(path: Path) -> int:
    return stat_safe(path).st_size


def resolve_safe(path: Path) -> Path:
    raw = str(path).replace("\\", "/")
    if _WINDOWS_ABS_RE.match(raw):
        return Path(raw)
    return path.expanduser().resolve(strict=False)


def absolute_safe(path: Path) -> Path:
    raw = str(path).replace("\\", "/")
    if _WINDOWS_ABS_RE.match(raw):
        return Path(raw)
    expanded = path.expanduser()
    if expanded.is_absolute():
        return expanded
    return Path.cwd() / expanded


def stat_safe(path: Path) -> os.stat_result:
    return path.lstat()


def stat_follow_safe(path: Path) -> os.stat_result:
    return path.stat()


def scandir_safe(path: Path) -> Iterator[Path]:
    with os.scandir(path) as entries:
        for entry in entries:
            yield Path(entry.path)


def scandir_with_stat_safe(path: Path) -> Iterator[ScandirEntry]:
    with os.scandir(path) as entries:
        for entry in entries:
            try:
                stat_result = entry.stat(follow_symlinks=False)
            except OSError:
                stat_result = None
            yield ScandirEntry(path=Path(entry.path), stat_result=stat_result)


def is_hidden(path: Path) -> bool:
    return any(part.startswith(".") or part in _HIDDEN_NAMES for part in path.parts)


__all__ = [
    "DENYLIST",
    "is_hidden",
    "open_readonly",
    "resolve_safe",
    "scandir_safe",
    "stat_follow_safe",
    "stat_safe",
]
