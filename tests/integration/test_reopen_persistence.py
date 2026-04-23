from __future__ import annotations

from pathlib import Path

from eodinga.config import RootConfig
from eodinga.content.registry import parse
from eodinga.core.watcher import WatchService
from eodinga.index import open_index
from eodinga.index.build import rebuild_index
from eodinga.index.writer import IndexWriter
from eodinga.query import search
from tests.integration._helpers import wait_for_query_hit


def test_reopen_after_live_create_preserves_query_hits_without_rebuild(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    root.mkdir()
    rebuild_index(db_path, [RootConfig(path=root)], content_enabled=True)

    conn = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root)

        created = root / "persisted-after-live-create.txt"
        created.write_text("persisted after live create\n", encoding="utf-8")
        elapsed = wait_for_query_hit(
            conn,
            service,
            writer,
            "persisted after live create",
            created,
            deadline_seconds=0.5,
        )
        live_hits = [hit.file.path for hit in search(conn, "persisted after live create", limit=5).hits]
    finally:
        service.stop()
        conn.close()

    reopened = open_index(db_path)
    try:
        reopened_hits = [
            hit.file.path for hit in search(reopened, "persisted after live create", limit=5).hits
        ]
    finally:
        reopened.close()

    assert elapsed <= 0.5
    assert live_hits == [created]
    assert reopened_hits == [created]


def test_reopen_after_multi_root_live_create_preserves_root_scope(tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "database" / "index.db"
    root_a.mkdir()
    root_b.mkdir()
    existing = root_a / "alpha-existing.txt"
    existing.write_text("alpha persisted reopen scope\n", encoding="utf-8")
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

        created = root_b / "beta-after-live-create.txt"
        created.write_text("beta persisted reopen scope\n", encoding="utf-8")
        elapsed = wait_for_query_hit(
            conn,
            service,
            writer,
            "beta persisted reopen scope",
            created,
            deadline_seconds=0.5,
        )
        live_global_hits = {
            hit.file.path for hit in search(conn, "persisted reopen scope", limit=5).hits
        }
        live_alpha_hits = {
            hit.file.path
            for hit in search(conn, "persisted reopen scope", limit=5, root=root_a).hits
        }
        live_beta_hits = {
            hit.file.path
            for hit in search(conn, "persisted reopen scope", limit=5, root=root_b).hits
        }
    finally:
        service.stop()
        conn.close()

    reopened = open_index(db_path)
    try:
        reopened_global_hits = {
            hit.file.path for hit in search(reopened, "persisted reopen scope", limit=5).hits
        }
        reopened_alpha_hits = {
            hit.file.path
            for hit in search(reopened, "persisted reopen scope", limit=5, root=root_a).hits
        }
        reopened_beta_hits = {
            hit.file.path
            for hit in search(reopened, "persisted reopen scope", limit=5, root=root_b).hits
        }
    finally:
        reopened.close()

    assert elapsed <= 0.5
    assert live_global_hits == {existing, created}
    assert live_alpha_hits == {existing}
    assert live_beta_hits == {created}
    assert reopened_global_hits == {existing, created}
    assert reopened_alpha_hits == {existing}
    assert reopened_beta_hits == {created}
