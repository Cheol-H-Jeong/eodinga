from __future__ import annotations

from pathlib import Path
from queue import Empty
from time import monotonic

from eodinga.index.writer import IndexWriter
from eodinga.query import search


def query_hit_paths(conn, query: str, *, limit: int = 5, root: Path | None = None) -> list[Path]:
    return [hit.file.path for hit in search(conn, query, limit=limit, root=root).hits]


def query_hit_names(conn, query: str, *, limit: int = 5, root: Path | None = None) -> list[str]:
    return [hit.file.name for hit in search(conn, query, limit=limit, root=root).hits]


def wait_for_query_hit(
    conn,
    service,
    writer: IndexWriter,
    *,
    record_loader,
    query: str,
    expected_path: Path,
    deadline_seconds: float,
    root: Path | None = None,
) -> float:
    started = monotonic()
    deadline = started + deadline_seconds
    while monotonic() < deadline:
        try:
            event = service.queue.get(timeout=0.05)
        except Empty:
            continue
        writer.apply_events([event], record_loader=record_loader)
        hits = query_hit_paths(conn, query, limit=5, root=root)
        if expected_path in hits:
            return min(monotonic() - started, deadline_seconds)
    raise AssertionError(f"{expected_path} did not become query-visible within {deadline_seconds:.3f}s")


def wait_for_query_miss(
    conn,
    service,
    writer: IndexWriter,
    *,
    record_loader,
    query: str,
    missing_path: Path,
    deadline_seconds: float,
    root: Path | None = None,
) -> float:
    started = monotonic()
    deadline = started + deadline_seconds
    while monotonic() < deadline:
        try:
            event = service.queue.get(timeout=0.05)
        except Empty:
            continue
        writer.apply_events([event], record_loader=record_loader)
        hits = query_hit_paths(conn, query, limit=5, root=root)
        if missing_path not in hits:
            return min(monotonic() - started, deadline_seconds)
    raise AssertionError(f"{missing_path} remained query-visible after {deadline_seconds:.3f}s")
