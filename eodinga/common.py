from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ParsedContent:
    title: str
    head_text: str
    body_text: str
    content_sha: bytes


@dataclass(frozen=True, slots=True)
class FileRecord:
    root_id: int
    path: Path
    parent_path: Path
    name: str
    name_lower: str
    ext: str
    size: int
    mtime: int
    ctime: int
    is_dir: bool
    is_symlink: bool
    content_hash: bytes | None = None
    indexed_at: int = 0
    id: int | None = None


@dataclass(frozen=True, slots=True)
class WatchEvent:
    event_type: str
    path: Path
    src_path: Path | None = None
    is_dir: bool = False
    root_path: Path | None = None
    happened_at: float = 0.0


@dataclass(frozen=True, slots=True)
class PathRules:
    include: tuple[str, ...] = ("**/*",)
    exclude: tuple[str, ...] = ()
    root: Path | None = None


@dataclass(frozen=True, slots=True)
class IndexStats:
    file_count: int
    dir_count: int
    content_count: int
    total_size: int
    roots: tuple[Path, ...] = field(default_factory=tuple)
