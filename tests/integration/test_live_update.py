from __future__ import annotations

from pathlib import Path

from eodinga.config import RootConfig
from eodinga.content.registry import parse
from eodinga.core.watcher import WatchService
from eodinga.index import open_index
from eodinga.index.build import rebuild_index
from eodinga.index.writer import IndexWriter
from tests.conftest import make_record
from tests.integration.helpers import query_hit_paths, wait_for_query_hit, wait_for_query_miss


def test_live_update_visible_to_search_within_500ms(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    root.mkdir()
    rebuild_index(db_path, [RootConfig(path=root)], content_enabled=True)

    conn = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root)

        created = root / "live-update.txt"
        created.write_text("live update integration coverage\n", encoding="utf-8")

        elapsed = wait_for_query_hit(
            conn,
            service,
            writer,
            record_loader=make_record,
            query="integration coverage",
            expected_path=created,
            deadline_seconds=0.5,
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
        service.start(root)

        initial_hits = query_hit_paths(conn, "delete integration coverage")
        target.unlink()

        elapsed = wait_for_query_miss(
            conn,
            service,
            writer,
            record_loader=make_record,
            query="delete integration coverage",
            missing_path=target,
            deadline_seconds=0.5,
        )
    finally:
        service.stop()
        conn.close()

    assert initial_hits == [target]
    assert elapsed <= 0.5


def test_live_modify_replaces_query_visibility_within_500ms(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    root.mkdir()
    target = root / "live-modify.txt"
    target.write_text("before live rewrite marker\n", encoding="utf-8")
    rebuild_index(db_path, [RootConfig(path=root)], content_enabled=True)

    conn = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root)

        initial_hits = query_hit_paths(conn, "before live rewrite")
        target.write_text("after live rewrite marker\n", encoding="utf-8")

        elapsed = wait_for_query_hit(
            conn,
            service,
            writer,
            record_loader=make_record,
            query="after live rewrite",
            expected_path=target,
            deadline_seconds=0.5,
        )
        previous_hits = query_hit_paths(conn, "before live rewrite")
        current_hits = query_hit_paths(conn, "after live rewrite")
    finally:
        service.stop()
        conn.close()

    assert initial_hits == [target]
    assert elapsed <= 0.5
    assert previous_hits == []
    assert current_hits == [target]


def test_live_delete_then_recreate_same_path_replaces_query_visibility_within_500ms(
    tmp_path: Path,
) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    root.mkdir()
    target = root / "live-recreate.txt"
    target.write_text("before recreate marker\n", encoding="utf-8")
    rebuild_index(db_path, [RootConfig(path=root)], content_enabled=True)

    conn = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root)

        initial_hits = query_hit_paths(conn, "before recreate marker")
        target.unlink()
        target.write_text("after recreate marker\n", encoding="utf-8")

        elapsed = wait_for_query_hit(
            conn,
            service,
            writer,
            record_loader=make_record,
            query="after recreate marker",
            expected_path=target,
            deadline_seconds=0.5,
        )
        stale_hits = query_hit_paths(conn, "before recreate marker")
        current_hits = query_hit_paths(conn, "after recreate marker")
    finally:
        service.stop()
        conn.close()

    assert initial_hits == [target]
    assert elapsed <= 0.5
    assert stale_hits == []
    assert current_hits == [target]


def test_live_same_root_move_updates_search_visibility_within_500ms(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    root.mkdir()
    source = root / "draft-note.txt"
    source.write_text("same root move integration marker\n", encoding="utf-8")
    rebuild_index(db_path, [RootConfig(path=root)], content_enabled=True)

    conn = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root)

        initial_hits = query_hit_paths(conn, "same root move integration")
        destination = root / "renamed-note.txt"
        source.rename(destination)

        appeared_elapsed = wait_for_query_hit(
            conn,
            service,
            writer,
            record_loader=make_record,
            query="same root move integration",
            expected_path=destination,
            deadline_seconds=0.5,
        )
        removed_elapsed = wait_for_query_miss(
            conn,
            service,
            writer,
            record_loader=make_record,
            query="same root move integration",
            missing_path=source,
            deadline_seconds=0.5,
        )
        source_path_hits = query_hit_paths(conn, "path:draft-note")
        destination_path_hits = query_hit_paths(conn, "path:renamed-note")
    finally:
        service.stop()
        conn.close()

    assert initial_hits == [source]
    assert appeared_elapsed <= 0.5
    assert removed_elapsed <= 0.5
    assert source_path_hits == []
    assert destination_path_hits == [destination]


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
        service.start(root_a)
        service.start(root_b)

        created = root_b / "beta-live-update.txt"
        created.write_text("beta scoped integration visibility\n", encoding="utf-8")

        elapsed = wait_for_query_hit(
            conn,
            service,
            writer,
            record_loader=make_record,
            query="scoped integration visibility",
            expected_path=created,
            deadline_seconds=0.5,
        )
        alpha_hits = query_hit_paths(conn, "scoped integration visibility", root=root_a)
        beta_hits = query_hit_paths(conn, "scoped integration visibility", root=root_b)
    finally:
        service.stop()
        conn.close()

    assert elapsed <= 0.5
    assert alpha_hits == []
    assert beta_hits == [created]


def test_live_cross_root_move_updates_global_and_root_scoped_queries(tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "database" / "index.db"
    root_a.mkdir()
    root_b.mkdir()
    moved = root_a / "moved-note.txt"
    moved.write_text("cross root move integration\n", encoding="utf-8")
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

        initial_alpha_hits = query_hit_paths(conn, "cross root move integration", root=root_a)
        destination = root_b / moved.name
        moved.rename(destination)

        appeared_elapsed = wait_for_query_hit(
            conn,
            service,
            writer,
            record_loader=make_record,
            query="cross root move integration",
            expected_path=destination,
            deadline_seconds=0.5,
        )
        removed_elapsed = wait_for_query_miss(
            conn,
            service,
            writer,
            record_loader=make_record,
            query="cross root move integration",
            missing_path=moved,
            deadline_seconds=0.5,
        )
        alpha_hits = query_hit_paths(conn, "cross root move integration", root=root_a)
        beta_hits = query_hit_paths(conn, "cross root move integration", root=root_b)
        all_hits = query_hit_paths(conn, "cross root move integration")
    finally:
        service.stop()
        conn.close()

    assert initial_alpha_hits == [moved]
    assert appeared_elapsed <= 0.5
    assert removed_elapsed <= 0.5
    assert alpha_hits == []
    assert beta_hits == [destination]
    assert all_hits == [destination]


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
        service.start(root_a)
        service.start(root_b)

        initial_hits = query_hit_paths(conn, "scoped integration deletion")
        initial_beta_hits = query_hit_paths(conn, "scoped integration deletion", root=root_b)
        target.unlink()

        elapsed = wait_for_query_miss(
            conn,
            service,
            writer,
            record_loader=make_record,
            query="scoped integration deletion",
            missing_path=target,
            deadline_seconds=0.5,
        )
        alpha_hits = query_hit_paths(conn, "scoped integration retention", root=root_a)
        beta_hits = query_hit_paths(conn, "scoped integration deletion", root=root_b)
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
        initial_hits = query_hit_paths(first_conn, "persisted restart", limit=3)
    finally:
        first_conn.close()

    reopened = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(reopened, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root)

        created = root / "after-reopen.txt"
        created.write_text("post reopen live update\n", encoding="utf-8")
        wait_for_query_hit(
            reopened,
            service,
            writer,
            record_loader=make_record,
            query="post reopen",
            expected_path=created,
            deadline_seconds=0.5,
        )
        reopened_hits = query_hit_paths(reopened, "persisted restart", limit=3)
    finally:
        service.stop()
        reopened.close()

    assert initial_hits == [existing]
    assert reopened_hits == [existing]
