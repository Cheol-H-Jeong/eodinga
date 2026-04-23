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


def test_reopen_after_removed_root_rebuild_accepts_live_updates_only_for_surviving_root(
    tmp_path: Path,
) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "database" / "index.db"

    root_a.mkdir()
    root_b.mkdir()
    (root_a / "alpha-existing.txt").write_text("trimmed root alpha survivor\n", encoding="utf-8")
    (root_b / "beta-pruned.txt").write_text("trimmed root beta removal\n", encoding="utf-8")

    rebuild_index(
        db_path,
        [RootConfig(path=root_a), RootConfig(path=root_b)],
        content_enabled=True,
    )
    rebuild_index(db_path, [RootConfig(path=root_a)], content_enabled=True)

    reopened = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(reopened, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root_a)

        created = root_a / "alpha-after-reopen.txt"
        created.write_text("trimmed root live update\n", encoding="utf-8")
        elapsed = wait_for_query_hit(
            reopened,
            service,
            writer,
            "trimmed root live update",
            created,
            deadline_seconds=0.5,
        )
        global_hits = {hit.file.path for hit in search(reopened, "trimmed root", limit=10).hits}
        alpha_hits = {
            hit.file.path
            for hit in search(reopened, "trimmed root", limit=10, root=root_a).hits
        }
        beta_hits = {
            hit.file.path
            for hit in search(reopened, "trimmed root", limit=10, root=root_b).hits
        }
        stored_roots = {
            Path(row[0]) for row in reopened.execute("SELECT path FROM roots ORDER BY id").fetchall()
        }
    finally:
        service.stop()
        reopened.close()

    assert elapsed <= 0.5
    assert global_hits == {root_a / "alpha-existing.txt", created}
    assert alpha_hits == {root_a / "alpha-existing.txt", created}
    assert beta_hits == set()
    assert stored_roots == {root_a}


def test_open_index_resumes_trimmed_stage_and_accepts_live_updates_for_surviving_root(
    tmp_path: Path,
) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    target_db = tmp_path / "database" / "index.db"
    staged_db = tmp_path / "database" / ".index.db.next"

    root_a.mkdir()
    root_b.mkdir()
    survivor = root_a / "alpha-resumed.txt"
    survivor.write_text("trimmed stage alpha survivor\n", encoding="utf-8")
    (root_b / "beta-pruned.txt").write_text("trimmed stage beta removal\n", encoding="utf-8")

    rebuild_index(
        target_db,
        [RootConfig(path=root_a), RootConfig(path=root_b)],
        content_enabled=True,
    )
    rebuild_index(staged_db, [RootConfig(path=root_a)], content_enabled=True)
    target_db.unlink()

    reopened = open_index(target_db)
    service = WatchService()
    try:
        initial_hits = {hit.file.path for hit in search(reopened, "trimmed stage", limit=10).hits}
        initial_alpha_hits = {
            hit.file.path
            for hit in search(reopened, "trimmed stage", limit=10, root=root_a).hits
        }
        initial_beta_hits = {
            hit.file.path
            for hit in search(reopened, "trimmed stage", limit=10, root=root_b).hits
        }

        writer = IndexWriter(reopened, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root_a)

        created = root_a / "alpha-after-resume.txt"
        created.write_text("trimmed stage live update\n", encoding="utf-8")
        elapsed = wait_for_query_hit(
            reopened,
            service,
            writer,
            "trimmed stage live update",
            created,
            deadline_seconds=0.5,
        )
        updated_hits = {hit.file.path for hit in search(reopened, "trimmed stage", limit=10).hits}
        stored_roots = {
            Path(row[0]) for row in reopened.execute("SELECT path FROM roots ORDER BY id").fetchall()
        }
    finally:
        service.stop()
        reopened.close()

    assert initial_hits == {survivor}
    assert initial_alpha_hits == {survivor}
    assert initial_beta_hits == set()
    assert elapsed <= 0.5
    assert updated_hits == {survivor, created}
    assert stored_roots == {root_a}
    assert not staged_db.exists()
