from __future__ import annotations

from pathlib import Path
from queue import Empty
from time import monotonic

from eodinga.core.watcher import WatchService
from eodinga.index.writer import IndexWriter
from eodinga.query import search
from tests.conftest import make_record


def wait_for_query_hit(
    conn,
    service: WatchService,
    writer: IndexWriter,
    query: str,
    expected_path: Path,
    deadline_seconds: float,
) -> float:
    started = monotonic()
    deadline = started + deadline_seconds
    while monotonic() < deadline:
        try:
            event = service.queue.get(timeout=0.05)
        except Empty:
            continue
        writer.apply_events([event], record_loader=make_record)
        hits = [hit.file.path for hit in search(conn, query, limit=5).hits]
        if expected_path in hits:
            return monotonic() - started
    raise AssertionError(f"{expected_path} did not become query-visible within {deadline_seconds:.3f}s")


def wait_for_query_miss(
    conn,
    service: WatchService,
    writer: IndexWriter,
    query: str,
    missing_path: Path,
    deadline_seconds: float,
) -> float:
    started = monotonic()
    deadline = started + deadline_seconds
    while monotonic() < deadline:
        try:
            event = service.queue.get(timeout=0.05)
        except Empty:
            continue
        writer.apply_events([event], record_loader=make_record)
        hits = [hit.file.path for hit in search(conn, query, limit=5).hits]
        if missing_path not in hits:
            return monotonic() - started
    raise AssertionError(f"{missing_path} remained query-visible after {deadline_seconds:.3f}s")
