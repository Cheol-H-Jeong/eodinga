from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from eodinga.content.base import ParsedContent


class FileRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int | None = None
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
    indexed_at: int


class WatchEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_type: str
    path: Path
    src_path: Path | None = None
    is_dir: bool = False
    root_path: Path | None = None
    happened_at: float = 0.0


class PathRules(BaseModel):
    model_config = ConfigDict(frozen=True)

    root: Path | None = None
    include: tuple[str, ...] = ("**/*",)
    exclude: tuple[str, ...] = ()


class IndexStats(BaseModel):
    model_config = ConfigDict(frozen=True)

    file_count: int = 0
    dir_count: int = 0
    content_count: int = 0
    total_size: int = 0
    roots: tuple[Path, ...] = ()


class SearchHit(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: Path
    parent_path: Path
    name: str
    ext: str = ""
    snippet: str | None = None
    highlighted_name: str | None = None
    highlighted_path: str | None = None


class QueryResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[SearchHit] = Field(default_factory=list)
    total: int = 0
    elapsed_ms: float = 0.0


class IndexingStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    phase: str = "idle"
    processed_files: int = 0
    total_files: int = 0
    current_root: Path | None = None


class SearchResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: Path
    score: float = 0.0
    snippet: str | None = None


class StatsSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: str | None = None
    generated_at: str | None = None
    started_at: str | None = None
    uptime_ms: float = 0.0
    pid: int = 0
    platform: str | None = None
    python: str | None = None
    files_indexed: int = 0
    documents_indexed: int = 0
    queries_served: int = 0
    parser_errors: int = 0
    watcher_events: int = 0
    commands_started: int = 0
    commands_completed: int = 0
    commands_failed: int = 0
    crashes_reported: int = 0
    crash_logs_written: int = 0
    query_latency_histogram: dict[str, object] = Field(default_factory=dict)
    command_latency_histogram: dict[str, object] = Field(default_factory=dict)
    commands: dict[str, dict[str, int]] = Field(default_factory=dict)
    exit_codes: dict[str, int] = Field(default_factory=dict)
    counters: dict[str, int] = Field(default_factory=dict)
    histograms: dict[str, dict[str, object]] = Field(default_factory=dict)
    roots: list[Path] = Field(default_factory=list)
    db_path: Path | None = None
    log_path: Path | None = None
    crash_dir: Path | None = None
    file_logging_enabled: bool = True


__all__ = [
    "FileRecord",
    "IndexStats",
    "IndexingStatus",
    "ParsedContent",
    "PathRules",
    "QueryResult",
    "SearchHit",
    "SearchResult",
    "StatsSnapshot",
    "WatchEvent",
]
