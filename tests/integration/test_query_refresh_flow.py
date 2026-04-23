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


def test_query_refresh_flow_updates_search_results_across_create_modify_delete(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    root.mkdir()
    stable = root / "stable.txt"
    stable.write_text("stable refresh baseline\n", encoding="utf-8")
    rebuild_index(db_path, [RootConfig(path=root)], content_enabled=True)

    conn = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root)

        assert query_hit_paths(conn, "stable refresh baseline") == [stable]

        target = root / "flow.txt"
        target.write_text("refresh journey draft\n", encoding="utf-8")
        created_elapsed = wait_for_query_hit(
            conn,
            service,
            writer,
            record_loader=make_record,
            query="refresh journey draft",
            expected_path=target,
            deadline_seconds=0.5,
        )

        target.write_text("refresh journey final\n", encoding="utf-8")
        modified_elapsed = wait_for_query_hit(
            conn,
            service,
            writer,
            record_loader=make_record,
            query="refresh journey final",
            expected_path=target,
            deadline_seconds=0.5,
        )

        target.unlink()
        deleted_elapsed = wait_for_query_miss(
            conn,
            service,
            writer,
            record_loader=make_record,
            query="refresh journey final",
            missing_path=target,
            deadline_seconds=0.5,
        )

        stable_hits = query_hit_paths(conn, "stable refresh baseline")
        draft_hits = query_hit_paths(conn, "refresh journey draft")
        final_hits = query_hit_paths(conn, "refresh journey final")
    finally:
        service.stop()
        conn.close()

    assert created_elapsed <= 0.5
    assert modified_elapsed <= 0.5
    assert deleted_elapsed <= 0.5
    assert stable_hits == [stable]
    assert draft_hits == []
    assert final_hits == []


def test_query_refresh_flow_cross_root_move_updates_scope_after_live_create(tmp_path: Path) -> None:
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

        created = root_a / "alpha-live.txt"
        created.write_text("multi stage root transfer\n", encoding="utf-8")
        create_elapsed = wait_for_query_hit(
            conn,
            service,
            writer,
            record_loader=make_record,
            query="multi stage root transfer",
            expected_path=created,
            deadline_seconds=0.5,
        )
        assert query_hit_paths(conn, "multi stage root transfer", root=root_a) == [created]
        assert query_hit_paths(conn, "multi stage root transfer", root=root_b) == []

        moved = root_b / created.name
        created.rename(moved)
        move_elapsed = wait_for_query_hit(
            conn,
            service,
            writer,
            record_loader=make_record,
            query="multi stage root transfer",
            expected_path=moved,
            deadline_seconds=0.5,
        )
        removed_elapsed = wait_for_query_miss(
            conn,
            service,
            writer,
            record_loader=make_record,
            query="multi stage root transfer",
            missing_path=created,
            deadline_seconds=0.5,
        )

        global_hits = query_hit_paths(conn, "multi stage root transfer")
        alpha_hits = query_hit_paths(conn, "multi stage root transfer", root=root_a)
        beta_hits = query_hit_paths(conn, "multi stage root transfer", root=root_b)
    finally:
        service.stop()
        conn.close()

    assert create_elapsed <= 0.5
    assert move_elapsed <= 0.5
    assert removed_elapsed <= 0.5
    assert global_hits == [moved]
    assert alpha_hits == []
    assert beta_hits == [moved]
