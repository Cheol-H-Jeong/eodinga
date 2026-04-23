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


def test_reopen_multi_root_recreate_same_path_replaces_scope_and_content(tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "database" / "index.db"
    root_a.mkdir()
    root_b.mkdir()
    survivor = root_a / "alpha-stable.txt"
    target = root_b / "beta-recreate.txt"
    survivor.write_text("alpha reopen survivor\n", encoding="utf-8")
    target.write_text("beta reopen before recreate\n", encoding="utf-8")
    rebuild_index(
        db_path,
        [RootConfig(path=root_a), RootConfig(path=root_b)],
        content_enabled=True,
    )

    first_conn = open_index(db_path)
    try:
        initial_hits = {hit.file.path for hit in search(first_conn, "beta reopen before recreate", limit=5).hits}
        initial_beta_hits = {
            hit.file.path
            for hit in search(first_conn, "beta reopen before recreate", limit=5, root=root_b).hits
        }
    finally:
        first_conn.close()

    reopened = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(reopened, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root_a)
        service.start(root_b)

        target.unlink()
        target.write_text("beta reopen after recreate\n", encoding="utf-8")

        appeared_elapsed = wait_for_query_hit(
            reopened,
            service,
            writer,
            "beta reopen after recreate",
            target,
            deadline_seconds=0.5,
        )
        removed_elapsed = wait_for_query_miss(
            reopened,
            service,
            writer,
            "beta reopen before recreate",
            target,
            deadline_seconds=0.5,
        )
        stale_hits = {
            hit.file.path for hit in search(reopened, "beta reopen before recreate", limit=5).hits
        }
        fresh_hits = {
            hit.file.path for hit in search(reopened, "beta reopen after recreate", limit=5).hits
        }
        alpha_hits = {hit.file.path for hit in search(reopened, "alpha reopen survivor", limit=5, root=root_a).hits}
        beta_hits = {
            hit.file.path for hit in search(reopened, "beta reopen after recreate", limit=5, root=root_b).hits
        }
    finally:
        service.stop()
        reopened.close()

    assert initial_hits == {target}
    assert initial_beta_hits == {target}
    assert appeared_elapsed <= 0.5
    assert removed_elapsed <= 0.5
    assert stale_hits == set()
    assert fresh_hits == {target}
    assert alpha_hits == {survivor}
    assert beta_hits == {target}
