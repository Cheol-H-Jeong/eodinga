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


def _wait_for_hits(
    conn,
    service: WatchService,
    writer: IndexWriter,
    query: str,
    expected_paths: set[Path],
    *,
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
        hits = {hit.file.path for hit in search(conn, query, limit=10).hits}
        if expected_paths.issubset(hits):
            return monotonic() - started
    raise AssertionError(f"{expected_paths} did not become query-visible within {deadline_seconds:.3f}s")


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


def test_multi_root_live_updates_from_each_root_become_query_visible(tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "database" / "index.db"

    root_a.mkdir()
    root_b.mkdir()
    rebuild_index(
        db_path,
        [RootConfig(path=root_a), RootConfig(path=root_b)],
        content_enabled=True,
    )

    conn = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root_a)
        service.start(root_b)

        alpha_update = root_a / "alpha-live.txt"
        beta_update = root_b / "beta-live.txt"
        alpha_update.write_text("cross root live update\n", encoding="utf-8")
        beta_update.write_text("cross root live update\n", encoding="utf-8")

        elapsed = _wait_for_hits(
            conn,
            service,
            writer,
            "cross root live update",
            {alpha_update, beta_update},
            deadline_seconds=0.5,
        )
    finally:
        service.stop()
        conn.close()

    assert elapsed <= 0.5
