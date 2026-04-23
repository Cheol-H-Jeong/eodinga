from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path
from queue import Empty
from time import monotonic

from eodinga.core.watcher import WatchService
from eodinga.index.writer import IndexWriter
from tests.conftest import make_record


def wait_for_applied_event(
    service: WatchService,
    writer: IndexWriter,
    *,
    record_loader: Callable[[Path], object | None],
    deadline_seconds: float,
    predicate: Callable[[], bool],
) -> float:
    started = monotonic()
    deadline = started + deadline_seconds
    while monotonic() < deadline:
        try:
            event = service.queue.get(timeout=0.05)
        except Empty:
            continue
        writer.apply_events([event], record_loader=record_loader)
        if predicate():
            return monotonic() - started
    raise AssertionError(f"condition not satisfied within {deadline_seconds:.3f}s")


def root_aware_record_loader(conn: sqlite3.Connection) -> Callable[[Path], object | None]:
    root_rows = [
        (Path(str(row[0])), int(row[1]))
        for row in conn.execute("SELECT path, id FROM roots ORDER BY LENGTH(path) DESC, id ASC")
    ]

    def load(path: Path) -> object | None:
        for root_path, root_id in root_rows:
            try:
                path.relative_to(root_path)
            except ValueError:
                continue
            return make_record(path, root_id=root_id)
        return make_record(path)

    return load
