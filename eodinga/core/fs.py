from __future__ import annotations

from pathlib import Path


def open_readonly(path: Path, mode: str = "rb"):
    if any(flag in mode for flag in ("w", "a", "+", "x")):
        raise ValueError("open_readonly only allows read modes")
    return path.open(mode)


def read_bytes(path: Path, max_bytes: int | None = None) -> bytes:
    with open_readonly(path, "rb") as handle:
        if max_bytes is None:
            return handle.read()
        return handle.read(max_bytes)


def file_size(path: Path) -> int:
    return path.stat().st_size

