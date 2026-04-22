from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class FileRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    root_id: int
    path: str
    parent_path: str
    name: str
    name_lower: str
    ext: str
    size: int
    mtime: int
    ctime: int
    is_dir: bool
    is_symlink: bool
    indexed_at: int
