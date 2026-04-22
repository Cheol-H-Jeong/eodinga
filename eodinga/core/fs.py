from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path
from typing import IO, Literal

__all__ = ["DENYLIST", "is_hidden", "open_readonly", "resolve_safe", "scandir_safe", "stat_safe"]

DENYLIST = frozenset(
    {
        "/proc",
        "/sys",
        "/dev",
        "/snap",
        "/run",
        "/var/cache",
        "/var/lib/docker",
        "/tmp",
        "~/.cache",
        "~/.local/share/Trash",
        "~/snap",
        "C:/Windows",
        "C:/$Recycle.Bin",
        "%SystemRoot%",
    }
)


def _normalize(path: Path) -> str:
    return str(path).replace("\\", "/")


def _expanded_patterns() -> tuple[str, ...]:
    home = Path.home()
    system_root = Path.home().drive + "/Windows" if Path.home().drive else "C:/Windows"
    expanded: list[str] = []
    for raw in DENYLIST:
        if raw == "%SystemRoot%":
            expanded.append(system_root)
            continue
        if raw.startswith("~/"):
            expanded.append(_normalize(home / raw[2:]))
            continue
        expanded.append(raw)
    return tuple(expanded)


def scandir_safe(path: Path):
    return path.expanduser().iterdir()


def stat_safe(path: Path):
    return path.expanduser().stat(follow_symlinks=False)


def open_readonly(path: Path, mode: Literal["rb", "r", "rt"] = "rb") -> IO[str] | IO[bytes]:
    if mode not in {"rb", "r", "rt"}:
        raise ValueError(f"unsupported readonly mode: {mode}")
    encoding = "utf-8" if mode in {"r", "rt"} else None
    return path.expanduser().open(mode=mode, encoding=encoding)


def is_hidden(path: Path) -> bool:
    return path.name.startswith(".") or any(
        fnmatch(_normalize(path), f"{pattern}*") for pattern in _expanded_patterns()
    )


def resolve_safe(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)
