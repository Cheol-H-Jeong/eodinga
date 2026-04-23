from __future__ import annotations

from pathlib import Path
from queue import Empty
from time import monotonic

from eodinga.config import RootConfig
from eodinga.content.registry import parse
from eodinga.core.watcher import WatchService
from eodinga.index import open_index
from eodinga.index.build import rebuild_index
from eodinga.index.writer import IndexWriter
from eodinga.query import search
from tests.conftest import make_record


def _wait_for_query_hit(
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
        hits = {hit.file.path for hit in search(conn, query, limit=5).hits}
        if expected_path in hits:
            return min(monotonic() - started, deadline_seconds)
    raise AssertionError(f"{expected_path} did not become query-visible within {deadline_seconds:.3f}s")


def _wait_for_query_miss(
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
        hits = {hit.file.path for hit in search(conn, query, limit=5).hits}
        if missing_path not in hits:
            return min(monotonic() - started, deadline_seconds)
    raise AssertionError(f"{missing_path} remained query-visible after {deadline_seconds:.3f}s")


def test_trimmed_multi_root_reopen_live_create_stays_in_surviving_scope(tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "database" / "index.db"
    root_a.mkdir()
    root_b.mkdir()
    survivor = root_a / "alpha-survivor.txt"
    removed_root_file = root_b / "beta-pruned.txt"
    survivor.write_text("trimmed root survivor\n", encoding="utf-8")
    removed_root_file.write_text("trimmed root pruned\n", encoding="utf-8")

    rebuild_index(
        db_path,
        [RootConfig(path=root_a), RootConfig(path=root_b)],
        content_enabled=True,
    )
    rebuild_index(db_path, [RootConfig(path=root_a)], content_enabled=True)

    reopened = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(reopened, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root_a)

        initial_hits = {hit.file.path for hit in search(reopened, "survivor", limit=10).hits}

        created = root_a / "alpha-created.txt"
        created.write_text("trimmed root live create\n", encoding="utf-8")
        elapsed = _wait_for_query_hit(
            reopened,
            service,
            writer,
            "trimmed root live create",
            created,
            deadline_seconds=0.5,
        )

        global_hits = {hit.file.path for hit in search(reopened, "live create", limit=10).hits}
        alpha_hits = {
            hit.file.path for hit in search(reopened, "live create", limit=10, root=root_a).hits
        }
        beta_hits = {
            hit.file.path for hit in search(reopened, "live create", limit=10, root=root_b).hits
        }
        pruned_hits = {hit.file.path for hit in search(reopened, "pruned", limit=10).hits}
        stored_roots = {
            Path(row[0]) for row in reopened.execute("SELECT path FROM roots ORDER BY id").fetchall()
        }
    finally:
        service.stop()
        reopened.close()

    assert initial_hits == {survivor}
    assert elapsed <= 0.5
    assert global_hits == {created}
    assert alpha_hits == {created}
    assert beta_hits == set()
    assert pruned_hits == set()
    assert stored_roots == {root_a}


def test_trimmed_multi_root_reopen_live_modify_stays_in_surviving_scope(tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "database" / "index.db"
    root_a.mkdir()
    root_b.mkdir()
    target = root_a / "alpha-rewrite.txt"
    removed_root_file = root_b / "beta-pruned.txt"
    target.write_text("trimmed root original text\n", encoding="utf-8")
    removed_root_file.write_text("trimmed root pruned\n", encoding="utf-8")

    rebuild_index(
        db_path,
        [RootConfig(path=root_a), RootConfig(path=root_b)],
        content_enabled=True,
    )
    rebuild_index(db_path, [RootConfig(path=root_a)], content_enabled=True)

    reopened = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(reopened, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root_a)

        initial_hits = {hit.file.path for hit in search(reopened, "original text", limit=10).hits}

        target.write_text("trimmed root rewritten text\n", encoding="utf-8")
        elapsed = _wait_for_query_hit(
            reopened,
            service,
            writer,
            "rewritten text",
            target,
            deadline_seconds=0.5,
        )

        stale_hits = {hit.file.path for hit in search(reopened, "original text", limit=10).hits}
        alpha_hits = {
            hit.file.path for hit in search(reopened, "rewritten text", limit=10, root=root_a).hits
        }
        beta_hits = {
            hit.file.path for hit in search(reopened, "rewritten text", limit=10, root=root_b).hits
        }
        pruned_hits = {hit.file.path for hit in search(reopened, "pruned", limit=10).hits}
        stored_roots = {
            Path(row[0]) for row in reopened.execute("SELECT path FROM roots ORDER BY id").fetchall()
        }
    finally:
        service.stop()
        reopened.close()

    assert initial_hits == {target}
    assert elapsed <= 0.5
    assert stale_hits == set()
    assert alpha_hits == {target}
    assert beta_hits == set()
    assert pruned_hits == set()
    assert stored_roots == {root_a}
