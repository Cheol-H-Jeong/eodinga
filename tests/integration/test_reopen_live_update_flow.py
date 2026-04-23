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


def test_reopen_after_live_modify_keeps_latest_query_state(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    root.mkdir()
    rebuild_index(db_path, [RootConfig(path=root)], content_enabled=True)

    conn = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root)

        target = root / "reopen-latest.txt"
        target.write_text("before reopen latest state\n", encoding="utf-8")
        created_elapsed = wait_for_query_hit(
            conn,
            service,
            writer,
            record_loader=make_record,
            query="before reopen latest state",
            expected_path=target,
            deadline_seconds=0.5,
        )

        target.write_text("after reopen latest state\n", encoding="utf-8")
        modified_elapsed = wait_for_query_hit(
            conn,
            service,
            writer,
            record_loader=make_record,
            query="after reopen latest state",
            expected_path=target,
            deadline_seconds=0.5,
        )

        before_reopen_old_hits = query_hit_paths(conn, "before reopen latest state")
        before_reopen_new_hits = query_hit_paths(conn, "after reopen latest state")
    finally:
        service.stop()
        conn.close()

    reopened = open_index(db_path)
    try:
        reopened_old_hits = query_hit_paths(reopened, "before reopen latest state")
        reopened_new_hits = query_hit_paths(reopened, "after reopen latest state")
    finally:
        reopened.close()

    assert created_elapsed <= 0.5
    assert modified_elapsed <= 0.5
    assert before_reopen_old_hits == []
    assert before_reopen_new_hits == [target]
    assert reopened_old_hits == []
    assert reopened_new_hits == [target]


def test_reopen_after_live_cross_root_move_keeps_latest_scope(tmp_path: Path) -> None:
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

        source = root_a / "reopen-transfer.txt"
        source.write_text("reopen latest transfer state\n", encoding="utf-8")
        create_elapsed = wait_for_query_hit(
            conn,
            service,
            writer,
            record_loader=make_record,
            query="reopen latest transfer state",
            expected_path=source,
            deadline_seconds=0.5,
        )

        destination = root_b / source.name
        source.rename(destination)
        move_elapsed = wait_for_query_hit(
            conn,
            service,
            writer,
            record_loader=make_record,
            query="reopen latest transfer state",
            expected_path=destination,
            deadline_seconds=0.5,
        )
        remove_elapsed = wait_for_query_miss(
            conn,
            service,
            writer,
            record_loader=make_record,
            query="reopen latest transfer state",
            missing_path=source,
            deadline_seconds=0.5,
        )
    finally:
        service.stop()
        conn.close()

    reopened = open_index(db_path)
    try:
        global_hits = query_hit_paths(reopened, "reopen latest transfer state")
        alpha_hits = query_hit_paths(reopened, "reopen latest transfer state", root=root_a)
        beta_hits = query_hit_paths(reopened, "reopen latest transfer state", root=root_b)
    finally:
        reopened.close()

    assert create_elapsed <= 0.5
    assert move_elapsed <= 0.5
    assert remove_elapsed <= 0.5
    assert global_hits == [destination]
    assert alpha_hits == []
    assert beta_hits == [destination]
