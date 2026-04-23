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

    generated_at: str | None = None
    process_started_at: str | None = None
    pid: int = 0
    thread_count: int = 0
    rss_bytes: int | None = None
    open_fd_count: int | None = None
    version: str = ""
    uptime_ms: float = 0.0
    files_indexed: int = 0
    documents_indexed: int = 0
    queries_served: int = 0
    queries_zero_results: int = 0
    queries_truncated: int = 0
    parser_errors: int = 0
    watcher_events: int = 0
    watcher_flushes: int = 0
    watcher_events_flushed: int = 0
    watcher_queue_full: int = 0
    watcher_enqueue_aborted: int = 0
    watcher_observers_started: int = 0
    watcher_observers_stopped: int = 0
    index_rebuilds_completed: int = 0
    commands_started: int = 0
    commands_completed: int = 0
    commands_failed: int = 0
    commands_interrupted: int = 0
    crashes_reported: int = 0
    crash_logs_written: int = 0
    crash_log_write_failures: int = 0
    crash_handlers_installed: int = 0
    logging_configurations: int = 0
    log_sinks_stderr_configured: int = 0
    log_sinks_file_configured: int = 0
    log_sinks_file_disabled: int = 0
    query_latency_histogram: dict[str, object] = Field(default_factory=dict)
    query_result_count_histogram: dict[str, object] = Field(default_factory=dict)
    command_latency_histogram: dict[str, object] = Field(default_factory=dict)
    watch_flush_batch_histogram: dict[str, object] = Field(default_factory=dict)
    watch_event_lag_histogram: dict[str, object] = Field(default_factory=dict)
    watcher_queue_backpressure_histogram: dict[str, object] = Field(default_factory=dict)
    index_rebuild_latency_histogram: dict[str, object] = Field(default_factory=dict)
    index_batch_size_histogram: dict[str, object] = Field(default_factory=dict)
    commands: dict[str, dict[str, int]] = Field(default_factory=dict)
    exit_codes: dict[str, int] = Field(default_factory=dict)
    crash_types: dict[str, int] = Field(default_factory=dict)
    parser_activity: dict[str, dict[str, int]] = Field(default_factory=dict)
    watcher_event_types: dict[str, int] = Field(default_factory=dict)
    counters: dict[str, int] = Field(default_factory=dict)
    histograms: dict[str, dict[str, object]] = Field(default_factory=dict)
    recent_snapshots: list[dict[str, object]] = Field(default_factory=list)
    recent_snapshot_count: int = 0
    recent_snapshot_limit: int = 0
    recent_snapshot_dropped: int = 0
    roots: list[Path] = Field(default_factory=list)
    db_path: Path | None = None
    log_path: Path | None = None
    log_file_exists: bool = False
    log_file_size_bytes: int | None = None
    log_rotation: str | int | None = None
    log_retention: str | int | None = None
    log_compression: str | None = None
    crash_dir: Path | None = None
    crash_log_count: int = 0
    crash_log_total_bytes: int = 0
    latest_crash_log: Path | None = None
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
