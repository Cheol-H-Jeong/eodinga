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


def test_reopen_after_pruning_root_accepts_live_updates_for_remaining_root(tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "database" / "index.db"
    root_a.mkdir()
    root_b.mkdir()
    survivor = root_a / "alpha-survivor.txt"
    pruned = root_b / "beta-pruned.txt"
    survivor.write_text("pruned root survivor\n", encoding="utf-8")
    pruned.write_text("pruned root survivor\n", encoding="utf-8")

    rebuild_index(
        db_path,
        [RootConfig(path=root_a), RootConfig(path=root_b)],
        content_enabled=True,
    )
    rebuild_index(db_path, [RootConfig(path=root_a)], content_enabled=True)

    reopened = open_index(db_path)
    service = WatchService()
    try:
        initial_hits = {hit.file.path for hit in search(reopened, "pruned root survivor", limit=5).hits}
        initial_beta_hits = {
            hit.file.path
            for hit in search(reopened, "pruned root survivor", limit=5, root=root_b).hits
        }

        writer = IndexWriter(reopened, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root_a)

        created = root_a / "alpha-after-prune.txt"
        created.write_text("post prune reopen live update\n", encoding="utf-8")
        elapsed = wait_for_query_hit(
            reopened,
            service,
            writer,
            "post prune reopen live update",
            created,
            deadline_seconds=0.5,
        )
        final_hits = {
            hit.file.path for hit in search(reopened, "post prune reopen live update", limit=5).hits
        }
        final_alpha_hits = {
            hit.file.path
            for hit in search(reopened, "post prune reopen live update", limit=5, root=root_a).hits
        }
        final_beta_hits = {
            hit.file.path
            for hit in search(reopened, "post prune reopen live update", limit=5, root=root_b).hits
        }
    finally:
        service.stop()
        reopened.close()

    assert initial_hits == {survivor}
    assert initial_beta_hits == set()
    assert elapsed <= 0.5
    assert final_hits == {created}
    assert final_alpha_hits == {created}
    assert final_beta_hits == set()


def test_reopen_after_pruning_root_keeps_trimmed_root_table_and_scoped_queries(tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "database" / "index.db"
    root_a.mkdir()
    root_b.mkdir()
    (root_a / "alpha-only.txt").write_text("alpha only after prune\n", encoding="utf-8")
    (root_b / "beta-only.txt").write_text("beta only after prune\n", encoding="utf-8")

    rebuild_index(
        db_path,
        [RootConfig(path=root_a), RootConfig(path=root_b)],
        content_enabled=True,
    )
    rebuild_index(db_path, [RootConfig(path=root_a)], content_enabled=True)

    reopened = open_index(db_path)
    try:
        all_hits = {hit.file.path for hit in search(reopened, "only after prune", limit=5).hits}
        alpha_hits = {
            hit.file.path for hit in search(reopened, "only after prune", limit=5, root=root_a).hits
        }
        beta_hits = {
            hit.file.path for hit in search(reopened, "only after prune", limit=5, root=root_b).hits
        }
        stored_roots = {
            Path(row[0]) for row in reopened.execute("SELECT path FROM roots ORDER BY id").fetchall()
        }
    finally:
        reopened.close()

    assert all_hits == {root_a / "alpha-only.txt"}
    assert alpha_hits == {root_a / "alpha-only.txt"}
    assert beta_hits == set()
    assert stored_roots == {root_a}
