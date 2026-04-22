from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict


class SearchResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: Path
    score: float = 0.0
    snippet: str | None = None


class StatsSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    files_indexed: int = 0
    documents_indexed: int = 0
    roots: list[Path] = []
    db_path: Path | None = None

