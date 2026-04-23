from __future__ import annotations

from pathlib import Path

from eodinga.config import RootConfig
from eodinga.content.registry import parse
from eodinga.core.watcher import WatchService
from eodinga.index import open_index
from eodinga.index.build import rebuild_index
from eodinga.index.writer import IndexWriter
from eodinga.query import search
from tests.integration._helpers import root_aware_record_loader, wait_for_applied_event


def test_live_update_visible_to_search_within_500ms(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    root.mkdir()
    rebuild_index(db_path, [RootConfig(path=root)], content_enabled=True)

    conn = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        record_loader = root_aware_record_loader(conn)
        service.start(root)

        created = root / "live-update.txt"
        created.write_text("live update integration coverage\n", encoding="utf-8")

        elapsed = wait_for_applied_event(
            service,
            writer,
            record_loader=record_loader,
            deadline_seconds=0.5,
            predicate=lambda: created
            in {hit.file.path for hit in search(conn, "integration coverage", limit=5).hits},
        )
    finally:
        service.stop()
        conn.close()

    assert elapsed <= 0.5


def test_live_delete_removed_from_search_within_500ms(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    root.mkdir()
    target = root / "live-delete.txt"
    target.write_text("live delete integration coverage\n", encoding="utf-8")
    rebuild_index(db_path, [RootConfig(path=root)], content_enabled=True)

    conn = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        record_loader = root_aware_record_loader(conn)
        service.start(root)

        initial_hits = [hit.file.path for hit in search(conn, "delete integration coverage", limit=5).hits]
        target.unlink()

        elapsed = wait_for_applied_event(
            service,
            writer,
            record_loader=record_loader,
            deadline_seconds=0.5,
            predicate=lambda: target
            not in {hit.file.path for hit in search(conn, "delete integration coverage", limit=5).hits},
        )
    finally:
        service.stop()
        conn.close()

    assert initial_hits == [target]
    assert elapsed <= 0.5


def test_live_update_visible_with_multi_root_watchers_and_root_scope(tmp_path: Path) -> None:
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
        record_loader = root_aware_record_loader(conn)
        service.start(root_a)
        service.start(root_b)

        created = root_b / "beta-live-update.txt"
        created.write_text("beta scoped integration visibility\n", encoding="utf-8")

        elapsed = wait_for_applied_event(
            service,
            writer,
            record_loader=record_loader,
            deadline_seconds=0.5,
            predicate=lambda: created
            in {hit.file.path for hit in search(conn, "scoped integration visibility", limit=5).hits},
        )
        alpha_hits = [
            hit.file.path
            for hit in search(conn, "scoped integration visibility", limit=5, root=root_a).hits
        ]
        beta_hits = [
            hit.file.path
            for hit in search(conn, "scoped integration visibility", limit=5, root=root_b).hits
        ]
    finally:
        service.stop()
        conn.close()

    assert elapsed <= 0.5
    assert alpha_hits == []
    assert beta_hits == [created]


def test_live_delete_removed_with_multi_root_watchers_and_root_scope(tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "database" / "index.db"
    root_a.mkdir()
    root_b.mkdir()
    survivor = root_a / "alpha-keep.txt"
    target = root_b / "beta-live-delete.txt"
    survivor.write_text("alpha scoped integration retention\n", encoding="utf-8")
    target.write_text("beta scoped integration deletion\n", encoding="utf-8")
    rebuild_index(
        db_path,
        [RootConfig(path=root_a), RootConfig(path=root_b)],
        content_enabled=True,
    )

    conn = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        record_loader = root_aware_record_loader(conn)
        service.start(root_a)
        service.start(root_b)

        initial_hits = [hit.file.path for hit in search(conn, "scoped integration deletion", limit=5).hits]
        initial_beta_hits = [
            hit.file.path
            for hit in search(conn, "scoped integration deletion", limit=5, root=root_b).hits
        ]
        target.unlink()

        elapsed = wait_for_applied_event(
            service,
            writer,
            record_loader=record_loader,
            deadline_seconds=0.5,
            predicate=lambda: target
            not in {hit.file.path for hit in search(conn, "scoped integration deletion", limit=5).hits},
        )
        alpha_hits = [
            hit.file.path
            for hit in search(conn, "scoped integration retention", limit=5, root=root_a).hits
        ]
        beta_hits = [
            hit.file.path
            for hit in search(conn, "scoped integration deletion", limit=5, root=root_b).hits
        ]
    finally:
        service.stop()
        conn.close()

    assert initial_hits == [target]
    assert initial_beta_hits == [target]
    assert elapsed <= 0.5
    assert alpha_hits == [survivor]
    assert beta_hits == []


def test_hot_restart_reopen_keeps_queries_and_accepts_live_updates(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    root.mkdir()
    existing = root / "existing.txt"
    existing.write_text("persisted restart query\n", encoding="utf-8")
    rebuild_index(db_path, [RootConfig(path=root)], content_enabled=True)

    first_conn = open_index(db_path)
    try:
        initial_hits = [hit.file.path for hit in search(first_conn, "persisted restart", limit=3).hits]
    finally:
        first_conn.close()

    reopened = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(reopened, parser_callback=lambda path: parse(path, max_body_chars=2048))
        record_loader = root_aware_record_loader(reopened)
        service.start(root)

        created = root / "after-reopen.txt"
        created.write_text("post reopen live update\n", encoding="utf-8")
        wait_for_applied_event(
            service,
            writer,
            record_loader=record_loader,
            deadline_seconds=0.5,
            predicate=lambda: created
            in {hit.file.path for hit in search(reopened, "post reopen", limit=5).hits},
        )
        reopened_hits = [hit.file.path for hit in search(reopened, "persisted restart", limit=3).hits]
    finally:
        service.stop()
        reopened.close()

    assert initial_hits == [existing]
    assert reopened_hits == [existing]
