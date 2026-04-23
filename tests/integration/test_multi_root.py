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
        hits = [hit.file.path for hit in search(conn, query, limit=5).hits]
        if expected_path in hits:
            return min(monotonic() - started, deadline_seconds)
    raise AssertionError(f"{expected_path} did not become query-visible within {deadline_seconds:.3f}s")


def test_multi_root_rebuild_indexes_all_roots_and_respects_root_scope(tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "database" / "index.db"

    root_a.mkdir()
    root_b.mkdir()
    (root_a / "alpha-shared.txt").write_text("shared launch note\n", encoding="utf-8")
    (root_b / "beta-shared.txt").write_text("shared launch note\n", encoding="utf-8")
    (root_b / "beta-only.txt").write_text("beta only content\n", encoding="utf-8")

    result = rebuild_index(
        db_path,
        [RootConfig(path=root_a), RootConfig(path=root_b)],
        content_enabled=True,
    )

    assert result.roots_indexed == 2

    conn = open_index(db_path)
    try:
        hits = {hit.file.path for hit in search(conn, "shared launch", limit=10).hits}
        alpha_hits = {hit.file.path for hit in search(conn, "shared launch", limit=10, root=root_a).hits}
        beta_hits = {hit.file.path for hit in search(conn, "shared launch", limit=10, root=root_b).hits}
        stored_roots = {
            Path(row[0]) for row in conn.execute("SELECT path FROM roots ORDER BY id").fetchall()
        }
        indexed_files = conn.execute("SELECT COUNT(*) FROM files WHERE is_dir = 0").fetchone()
    finally:
        conn.close()

    assert hits == {root_a / "alpha-shared.txt", root_b / "beta-shared.txt"}
    assert alpha_hits == {root_a / "alpha-shared.txt"}
    assert beta_hits == {root_b / "beta-shared.txt"}
    assert stored_roots == {root_a, root_b}
    assert indexed_files is not None and int(indexed_files[0]) == 3


def test_multi_root_rebuild_replaces_removed_root_content_and_scope(tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "database" / "index.db"

    root_a.mkdir()
    root_b.mkdir()
    alpha = root_a / "alpha-keep.txt"
    beta = root_b / "beta-drop.txt"
    alpha.write_text("shared rebuild survivor\n", encoding="utf-8")
    beta.write_text("shared rebuild survivor\n", encoding="utf-8")

    rebuild_index(
        db_path,
        [RootConfig(path=root_a), RootConfig(path=root_b)],
        content_enabled=True,
    )
    rebuild_index(db_path, [RootConfig(path=root_a)], content_enabled=True)

    conn = open_index(db_path)
    try:
        hits = {hit.file.path for hit in search(conn, "shared rebuild survivor", limit=10).hits}
        alpha_hits = {hit.file.path for hit in search(conn, "shared rebuild survivor", limit=10, root=root_a).hits}
        beta_hits = {hit.file.path for hit in search(conn, "shared rebuild survivor", limit=10, root=root_b).hits}
        stored_roots = {
            Path(row[0]) for row in conn.execute("SELECT path FROM roots ORDER BY id").fetchall()
        }
    finally:
        conn.close()

    assert hits == {alpha}
    assert alpha_hits == {alpha}
    assert beta_hits == set()
    assert stored_roots == {root_a}


def test_multi_root_reopen_after_removed_root_rebuild_keeps_trimmed_scope(tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "database" / "index.db"

    root_a.mkdir()
    root_b.mkdir()
    alpha = root_a / "alpha-survivor.txt"
    beta = root_b / "beta-pruned.txt"
    alpha.write_text("reopen trimmed root survivor\n", encoding="utf-8")
    beta.write_text("reopen trimmed root survivor\n", encoding="utf-8")

    rebuild_index(
        db_path,
        [RootConfig(path=root_a), RootConfig(path=root_b)],
        content_enabled=True,
    )
    rebuild_index(db_path, [RootConfig(path=root_a)], content_enabled=True)

    reopened = open_index(db_path)
    try:
        hits = {hit.file.path for hit in search(reopened, "reopen trimmed root survivor", limit=10).hits}
        alpha_hits = {
            hit.file.path
            for hit in search(reopened, "reopen trimmed root survivor", limit=10, root=root_a).hits
        }
        beta_hits = {
            hit.file.path
            for hit in search(reopened, "reopen trimmed root survivor", limit=10, root=root_b).hits
        }
        stored_roots = {
            Path(row[0]) for row in reopened.execute("SELECT path FROM roots ORDER BY id").fetchall()
        }
    finally:
        reopened.close()

    assert hits == {alpha}
    assert alpha_hits == {alpha}
    assert beta_hits == set()
    assert stored_roots == {root_a}


def test_multi_root_reopen_after_removed_root_rebuild_accepts_surviving_root_live_updates(
    tmp_path: Path,
) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "database" / "index.db"

    root_a.mkdir()
    root_b.mkdir()
    alpha = root_a / "alpha-survivor.txt"
    beta = root_b / "beta-pruned.txt"
    alpha.write_text("surviving root baseline\n", encoding="utf-8")
    beta.write_text("pruned root baseline\n", encoding="utf-8")

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

        created = root_a / "alpha-fresh.txt"
        created.write_text("surviving root live update\n", encoding="utf-8")
        elapsed = _wait_for_query_hit(
            reopened,
            service,
            writer,
            "surviving root live update",
            created,
            deadline_seconds=0.5,
        )
        alpha_hits = {
            hit.file.path
            for hit in search(reopened, "surviving root live update", limit=5, root=root_a).hits
        }
        beta_hits = {
            hit.file.path
            for hit in search(reopened, "surviving root live update", limit=5, root=root_b).hits
        }
        stored_roots = {
            Path(row[0]) for row in reopened.execute("SELECT path FROM roots ORDER BY id").fetchall()
        }
    finally:
        service.stop()
        reopened.close()

    assert elapsed <= 0.5
    assert alpha_hits == {created}
    assert beta_hits == set()
    assert stored_roots == {root_a}
