from __future__ import annotations

from contextlib import closing
from pathlib import Path
from queue import Empty
from time import monotonic, sleep

from eodinga.config import RootConfig
from eodinga.content.registry import parse
from eodinga.core.watcher import WatchService
from eodinga.index.build import rebuild_index
from eodinga.index.storage import open_index
from eodinga.index.writer import IndexWriter
from eodinga.query import search
from tests.conftest import make_record


def _drain_events(service: WatchService, timeout_s: float) -> list:
    deadline = monotonic() + timeout_s
    while True:
        remaining = deadline - monotonic()
        if remaining <= 0:
            return []
        try:
            first = service.queue.get(timeout=min(remaining, 0.05))
            break
        except Empty:
            continue
    events = [first]
    while True:
        try:
            events.append(service.queue.get_nowait())
        except Empty:
            return events


def _apply_pending_events(db_path: Path, service: WatchService) -> int:
    events = _drain_events(service, timeout_s=0.05)
    if not events:
        return 0
    with closing(open_index(db_path)) as conn:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        return writer.apply_events(events, record_loader=make_record)


def _query_hit_names(db_path: Path, query: str) -> list[str]:
    with closing(open_index(db_path)) as conn:
        return [hit.file.name for hit in search(conn, query, limit=5).hits]


def test_watchdog_live_update_surfaces_new_file_within_500ms(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    db_path = tmp_path / "index.db"
    existing = root / "alpha.txt"
    existing.write_text("baseline note\n", encoding="utf-8")
    rebuild_index(db_path, [RootConfig(path=root)])

    service = WatchService()
    service.start(root)
    try:
        created = root / "beta.txt"
        created.write_text("watchdog fresh result\n", encoding="utf-8")

        deadline = monotonic() + 0.5
        processed = 0
        while monotonic() < deadline:
            processed += _apply_pending_events(db_path, service)
            if _query_hit_names(db_path, "fresh result") == ["beta.txt"]:
                break
            sleep(0.01)
        else:
            raise AssertionError("watchdog update did not reach query results within 500ms")
    finally:
        service.stop()

    assert processed >= 1
    assert _query_hit_names(db_path, "baseline") == ["alpha.txt"]
    assert _query_hit_names(db_path, "fresh result") == ["beta.txt"]
