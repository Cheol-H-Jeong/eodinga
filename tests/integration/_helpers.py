from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from queue import Empty
from time import monotonic

from eodinga.common import WatchEvent
from eodinga.core.watcher import WatchService
from eodinga.index.writer import IndexWriter
from eodinga.query import search
from tests.conftest import make_record


def drain_and_apply_events(
    conn,
    service: WatchService,
    writer: IndexWriter,
    *,
    timeout_seconds: float,
    on_event: Callable[[], None] | None = None,
) -> list[WatchEvent]:
    started = monotonic()
    deadline = started + timeout_seconds
    applied: list[WatchEvent] = []
    while monotonic() < deadline:
        try:
            event = service.queue.get(timeout=0.05)
        except Empty:
            continue
        writer.apply_events([event], record_loader=make_record)
        applied.append(event)
        if on_event is not None:
            on_event()
    return applied


def wait_for_query_hit(
    conn,
    service: WatchService,
    writer: IndexWriter,
    query: str,
    expected_path: Path,
    *,
    deadline_seconds: float,
) -> float:
    started = monotonic()

    def _matches() -> bool:
        hits = [hit.file.path for hit in search(conn, query, limit=5).hits]
        return expected_path in hits

    if _matches():
        return 0.0
    deadline = started + deadline_seconds
    while monotonic() < deadline:
        try:
            event = service.queue.get(timeout=0.05)
        except Empty:
            continue
        writer.apply_events([event], record_loader=make_record)
        if _matches():
            return min(monotonic() - started, deadline_seconds)
    raise AssertionError(f"{expected_path} did not become query-visible within {deadline_seconds:.3f}s")


def wait_for_query_miss(
    conn,
    service: WatchService,
    writer: IndexWriter,
    query: str,
    missing_path: Path,
    *,
    deadline_seconds: float,
) -> float:
    started = monotonic()

    def _matches() -> bool:
        hits = [hit.file.path for hit in search(conn, query, limit=5).hits]
        return missing_path not in hits

    if _matches():
        return 0.0
    deadline = started + deadline_seconds
    while monotonic() < deadline:
        try:
            event = service.queue.get(timeout=0.05)
        except Empty:
            continue
        writer.apply_events([event], record_loader=make_record)
        if _matches():
            return min(monotonic() - started, deadline_seconds)
    raise AssertionError(f"{missing_path} remained query-visible after {deadline_seconds:.3f}s")
