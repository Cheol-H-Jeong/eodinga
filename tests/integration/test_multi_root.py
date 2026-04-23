from __future__ import annotations

from pathlib import Path

from eodinga.config import RootConfig
from eodinga.content.registry import parse
from eodinga.core.watcher import WatchService
from eodinga.index import open_index
from eodinga.index.build import rebuild_index
from eodinga.index.writer import IndexWriter
from eodinga.query import search
from tests.integration.test_live_update import _wait_for_query_hit


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


def test_multi_root_live_update_persists_across_reopen_without_rebuild(tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "database" / "index.db"

    root_a.mkdir()
    root_b.mkdir()
    existing_a = root_a / "alpha-shared.txt"
    existing_b = root_b / "beta-shared.txt"
    existing_a.write_text("alpha persisted search\n", encoding="utf-8")
    existing_b.write_text("beta persisted search\n", encoding="utf-8")
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

        created = root_b / "beta-live.txt"
        created.write_text("beta live update after rebuild\n", encoding="utf-8")
        elapsed = _wait_for_query_hit(
            conn,
            service,
            writer,
            "beta live update after rebuild",
            created,
            deadline_seconds=0.5,
        )
        scoped_hits = {
            hit.file.path
            for hit in search(conn, "beta live update after rebuild", limit=5, root=root_b).hits
        }
        all_hits = {hit.file.path for hit in search(conn, "persisted search", limit=5).hits}
    finally:
        service.stop()
        conn.close()

    reopened = open_index(db_path)
    try:
        reopened_hits = {
            hit.file.path for hit in search(reopened, "beta live update after rebuild", limit=5).hits
        }
        reopened_beta_hits = {
            hit.file.path
            for hit in search(reopened, "beta live update after rebuild", limit=5, root=root_b).hits
        }
    finally:
        reopened.close()

    assert elapsed <= 0.5
    assert scoped_hits == {created}
    assert all_hits == {existing_a, existing_b}
    assert reopened_hits == {created}
    assert reopened_beta_hits == {created}
