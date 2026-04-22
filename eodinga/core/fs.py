from __future__ import annotations

from pathlib import Path
from typing import IO


def open_readonly(path: Path, mode: str = "rb", encoding: str | None = None) -> IO[str] | IO[bytes]:
    if any(flag in mode for flag in ("w", "a", "+", "x")):
        raise ValueError("open_readonly only supports read modes")
    return path.open(mode=mode, encoding=encoding)


def exists(path: Path) -> bool:
    return path.exists()


def is_dir(path: Path) -> bool:
    return path.is_dir()


def is_file(path: Path) -> bool:
    return path.is_file()

