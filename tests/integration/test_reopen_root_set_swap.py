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


def test_reopen_after_root_set_swap_keeps_new_scope_and_accepts_live_updates(tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    root_c = tmp_path / "gamma-root"
    db_path = tmp_path / "database" / "index.db"
    root_a.mkdir()
    root_b.mkdir()
    root_c.mkdir()
    alpha = root_a / "alpha-removed.txt"
    beta = root_b / "beta-kept.txt"
    gamma = root_c / "gamma-added.txt"
    alpha.write_text("swapped root query\n", encoding="utf-8")
    beta.write_text("swapped root query\n", encoding="utf-8")
    gamma.write_text("swapped root query\n", encoding="utf-8")

    rebuild_index(
        db_path,
        [RootConfig(path=root_a), RootConfig(path=root_b)],
        content_enabled=True,
    )
    rebuild_index(
        db_path,
        [RootConfig(path=root_b), RootConfig(path=root_c)],
        content_enabled=True,
    )

    reopened = open_index(db_path)
    service = WatchService()
    try:
        initial_hits = {hit.file.path for hit in search(reopened, "swapped root query", limit=5).hits}
        initial_alpha_hits = {
            hit.file.path for hit in search(reopened, "swapped root query", limit=5, root=root_a).hits
        }
        initial_beta_hits = {
            hit.file.path for hit in search(reopened, "swapped root query", limit=5, root=root_b).hits
        }
        initial_gamma_hits = {
            hit.file.path for hit in search(reopened, "swapped root query", limit=5, root=root_c).hits
        }

        writer = IndexWriter(reopened, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root_b)
        service.start(root_c)

        created = root_c / "gamma-live.txt"
        created.write_text("swapped root live update\n", encoding="utf-8")
        elapsed = wait_for_query_hit(
            reopened,
            service,
            writer,
            "swapped root live update",
            created,
            deadline_seconds=0.5,
        )
        final_hits = {
            hit.file.path for hit in search(reopened, "swapped root live update", limit=5).hits
        }
        final_beta_hits = {
            hit.file.path
            for hit in search(reopened, "swapped root live update", limit=5, root=root_b).hits
        }
        final_gamma_hits = {
            hit.file.path
            for hit in search(reopened, "swapped root live update", limit=5, root=root_c).hits
        }
        final_alpha_hits = {
            hit.file.path
            for hit in search(reopened, "swapped root live update", limit=5, root=root_a).hits
        }
    finally:
        service.stop()
        reopened.close()

    assert initial_hits == {beta, gamma}
    assert initial_alpha_hits == set()
    assert initial_beta_hits == {beta}
    assert initial_gamma_hits == {gamma}
    assert elapsed <= 0.5
    assert final_hits == {created}
    assert final_beta_hits == set()
    assert final_gamma_hits == {created}
    assert final_alpha_hits == set()


def test_reopen_after_root_set_swap_persists_replaced_root_table(tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    root_c = tmp_path / "gamma-root"
    db_path = tmp_path / "database" / "index.db"
    root_a.mkdir()
    root_b.mkdir()
    root_c.mkdir()
    (root_a / "alpha-old.txt").write_text("old root result\n", encoding="utf-8")
    (root_b / "beta-current.txt").write_text("current root result\n", encoding="utf-8")
    (root_c / "gamma-current.txt").write_text("current root result\n", encoding="utf-8")

    rebuild_index(
        db_path,
        [RootConfig(path=root_a), RootConfig(path=root_b)],
        content_enabled=True,
    )
    rebuild_index(
        db_path,
        [RootConfig(path=root_b), RootConfig(path=root_c)],
        content_enabled=True,
    )

    reopened = open_index(db_path)
    try:
        current_hits = {hit.file.path for hit in search(reopened, "current root result", limit=5).hits}
        old_hits = {hit.file.path for hit in search(reopened, "old root result", limit=5).hits}
        stored_roots = {
            Path(row[0]) for row in reopened.execute("SELECT path FROM roots ORDER BY id").fetchall()
        }
    finally:
        reopened.close()

    assert current_hits == {root_b / "beta-current.txt", root_c / "gamma-current.txt"}
    assert old_hits == set()
    assert stored_roots == {root_b, root_c}
