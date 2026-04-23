from __future__ import annotations

from pathlib import Path

from eodinga.config import RootConfig
from eodinga.content.registry import parse
from eodinga.core.watcher import WatchService
from eodinga.index import open_index
from eodinga.index.build import rebuild_index
from eodinga.index.writer import IndexWriter
from eodinga.query import search
from tests.integration._helpers import wait_for_query_hit, wait_for_query_miss


def test_round_trip_live_create_modify_delete_updates_queries(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "index.db"
    root.mkdir()
    rebuild_index(db_path, [RootConfig(path=root)], content_enabled=True)

    conn = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root)

        target = root / "round-trip.txt"
        target.write_text("createonlytoken initial marker\n", encoding="utf-8")
        create_elapsed = wait_for_query_hit(
            conn,
            service,
            writer,
            "createonlytoken",
            target,
            deadline_seconds=0.5,
        )

        target.write_text("modifyonlytoken replacement marker\n", encoding="utf-8")
        modify_elapsed = wait_for_query_hit(
            conn,
            service,
            writer,
            "modifyonlytoken",
            target,
            deadline_seconds=0.5,
        )
        stale_elapsed = wait_for_query_miss(
            conn,
            service,
            writer,
            "createonlytoken",
            target,
            deadline_seconds=0.5,
        )

        target.unlink()
        delete_elapsed = wait_for_query_miss(
            conn,
            service,
            writer,
            "modifyonlytoken",
            target,
            deadline_seconds=0.5,
        )
    finally:
        service.stop()
        conn.close()

    assert create_elapsed <= 0.5
    assert modify_elapsed <= 0.5
    assert stale_elapsed <= 0.5
    assert delete_elapsed <= 0.5


def test_round_trip_reopen_cross_root_move_then_delete_clears_all_scopes(tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "index.db"
    root_a.mkdir()
    root_b.mkdir()
    moved = root_a / "handoff.txt"
    moved.write_text("reopen round trip handoff\n", encoding="utf-8")
    rebuild_index(
        db_path,
        [RootConfig(path=root_a), RootConfig(path=root_b)],
        content_enabled=True,
    )

    reopened = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(reopened, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root_a)
        service.start(root_b)

        destination = root_b / moved.name
        moved.rename(destination)
        appeared_elapsed = wait_for_query_hit(
            reopened,
            service,
            writer,
            "reopen round trip handoff",
            destination,
            deadline_seconds=0.5,
        )
        removed_elapsed = wait_for_query_miss(
            reopened,
            service,
            writer,
            "reopen round trip handoff",
            moved,
            deadline_seconds=0.5,
        )

        destination.unlink()
        delete_elapsed = wait_for_query_miss(
            reopened,
            service,
            writer,
            "reopen round trip handoff",
            destination,
            deadline_seconds=0.5,
        )
        global_hits = {
            hit.file.path for hit in search(reopened, "reopen round trip handoff", limit=5).hits
        }
        alpha_hits = {
            hit.file.path
            for hit in search(reopened, "reopen round trip handoff", limit=5, root=root_a).hits
        }
        beta_hits = {
            hit.file.path
            for hit in search(reopened, "reopen round trip handoff", limit=5, root=root_b).hits
        }
    finally:
        service.stop()
        reopened.close()

    assert appeared_elapsed <= 0.5
    assert removed_elapsed <= 0.5
    assert delete_elapsed <= 0.5
    assert global_hits == set()
    assert alpha_hits == set()
    assert beta_hits == set()
