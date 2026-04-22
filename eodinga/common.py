from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class SearchHit(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    path: Path
    name: str
    parent_path: Path = Field(default_factory=Path)
    ext: str = ""
    size: int = 0
    mtime: int = 0
    score: float = 0.0
    highlighted_name: str = ""
    highlighted_path: str = ""


class QueryResult(BaseModel):
    items: list[SearchHit] = Field(default_factory=list)
    total: int = 0
    elapsed_ms: float = 0.0

