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


def _wait_for_query_hit(db_path: Path, query: str, expected_name: str, service: WatchService) -> int:
    deadline = monotonic() + 0.5
    processed = 0
    while monotonic() < deadline:
        processed += _apply_pending_events(db_path, service)
        if expected_name in _query_hit_names(db_path, query):
            return processed
        sleep(0.01)
    raise AssertionError(f"{expected_name} did not appear for query {query!r} within 500ms")


def test_multi_root_live_update_indexes_changes_from_each_root(tmp_path: Path) -> None:
    alpha_root = tmp_path / "alpha"
    beta_root = tmp_path / "beta"
    alpha_root.mkdir()
    beta_root.mkdir()
    (alpha_root / "alpha.txt").write_text("alpha baseline\n", encoding="utf-8")
    (beta_root / "beta.txt").write_text("beta baseline\n", encoding="utf-8")
    db_path = tmp_path / "index.db"
    rebuild_index(db_path, [RootConfig(path=alpha_root), RootConfig(path=beta_root)])

    service = WatchService()
    service.start(alpha_root)
    service.start(beta_root)
    try:
        alpha_new = alpha_root / "alpha-fresh.txt"
        beta_new = beta_root / "beta-fresh.txt"
        alpha_new.write_text("alpha fresh live update\n", encoding="utf-8")
        beta_new.write_text("beta fresh live update\n", encoding="utf-8")

        processed = _wait_for_query_hit(db_path, "alpha fresh", "alpha-fresh.txt", service)
        processed += _wait_for_query_hit(db_path, "beta fresh", "beta-fresh.txt", service)
    finally:
        service.stop()

    assert processed >= 2
    assert _query_hit_names(db_path, "alpha baseline") == ["alpha.txt"]
    assert _query_hit_names(db_path, "beta baseline") == ["beta.txt"]


def test_hot_restart_after_live_update_keeps_queryable_changes(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    original = root / "original.txt"
    original.write_text("restart baseline\n", encoding="utf-8")
    db_path = tmp_path / "index.db"
    rebuild_index(db_path, [RootConfig(path=root)])

    service = WatchService()
    service.start(root)
    try:
        refreshed = root / "refreshed.txt"
        refreshed.write_text("restart live update\n", encoding="utf-8")
        processed = _wait_for_query_hit(db_path, "live update", "refreshed.txt", service)
    finally:
        service.stop()

    assert processed >= 1

    with closing(open_index(db_path)) as reopened:
        hits = [hit.file.name for hit in search(reopened, "restart live update", limit=5).hits]

    assert hits == ["refreshed.txt"]
