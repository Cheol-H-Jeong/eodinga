from __future__ import annotations

import json
import shutil
from pathlib import Path
from queue import Empty
from time import monotonic

from eodinga.config import RootConfig
from eodinga.common import PathRules
from eodinga.content.registry import parse
from eodinga.core.watcher import WatchService
from eodinga.core.walker import walk_batched
from eodinga.index import open_index
from eodinga.index.build import rebuild_index
from eodinga.index.storage import has_stale_wal
from eodinga.index.writer import IndexWriter
from eodinga.query import search
from tests.conftest import make_record


def _wait_for_query_hit(
    conn,
    service: WatchService,
    writer: IndexWriter,
    query: str,
    expected_path: Path,
    deadline_seconds: float,
) -> float:
    started = monotonic()
    deadline = started + deadline_seconds
    while monotonic() < deadline:
        try:
            event = service.queue.get(timeout=0.05)
        except Empty:
            continue
        writer.apply_events([event], record_loader=make_record)
        hits = [hit.file.path for hit in search(conn, query, limit=5).hits]
        if expected_path in hits:
            return min(monotonic() - started, deadline_seconds)
    raise AssertionError(f"{expected_path} did not become query-visible within {deadline_seconds:.3f}s")


def _result_names(payload: dict[str, object]) -> list[str]:
    results = payload["results"]
    assert isinstance(results, list)
    names: list[str] = []
    for item in results:
        assert isinstance(item, dict)
        raw_path = item["path"]
        assert isinstance(raw_path, str)
        names.append(Path(raw_path).name)
    return names


def test_cli_index_search_live_update_research_flow(cli_runner, tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    existing = root / "existing.txt"
    existing.write_text("persisted cli launch note\n", encoding="utf-8")
    db_path = tmp_path / "index.db"

    index_result = cli_runner("--db", str(db_path), "index", "--root", str(root), "--rebuild")

    assert index_result.returncode == 0
    index_payload = json.loads(index_result.stdout)
    assert index_payload["files_indexed"] >= 1

    first_search = cli_runner("--db", str(db_path), "search", "persisted cli launch", "--json")

    assert first_search.returncode == 0
    assert _result_names(json.loads(first_search.stdout)) == ["existing.txt"]

    conn = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root)

        created = root / "live-added.txt"
        created.write_text("cli live update marker\n", encoding="utf-8")

        elapsed = _wait_for_query_hit(
            conn,
            service,
            writer,
            "cli live update marker",
            created,
            deadline_seconds=0.5,
        )
    finally:
        service.stop()
        conn.close()

    assert elapsed <= 0.5

    second_search = cli_runner("--db", str(db_path), "search", "cli live update marker", "--json")
    stats_result = cli_runner("--db", str(db_path), "stats", "--json")

    assert second_search.returncode == 0
    assert _result_names(json.loads(second_search.stdout)) == ["live-added.txt"]
    assert stats_result.returncode == 0
    stats_payload = json.loads(stats_result.stdout)
    assert stats_payload["documents_indexed"] == 2
    assert stats_payload["roots"] == [str(root)]


def test_cli_search_resumes_interrupted_build_without_reindex(cli_runner, tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    target_db = tmp_path / "database" / "index.db"
    staged_db = tmp_path / "database" / ".index.db.next"
    root.mkdir()
    existing = root / "recovered.txt"
    existing.write_text("interrupted staged build recovery\n", encoding="utf-8")

    rebuild_index(target_db, [RootConfig(path=root)], content_enabled=True)
    rebuild_index(staged_db, [RootConfig(path=root)], content_enabled=True)
    target_db.unlink()
    assert staged_db.exists()

    search_result = cli_runner(
        "--db",
        str(target_db),
        "search",
        "interrupted staged build recovery",
        "--json",
    )
    stats_result = cli_runner("--db", str(target_db), "stats", "--json")

    assert search_result.returncode == 0
    assert _result_names(json.loads(search_result.stdout)) == ["recovered.txt"]
    assert stats_result.returncode == 0
    stats_payload = json.loads(stats_result.stdout)
    assert stats_payload["documents_indexed"] == 1
    assert stats_payload["roots"] == [str(root)]
    assert not staged_db.exists()


def test_cli_search_recovers_stale_wal_and_preserves_followup_queries(
    cli_runner,
    tmp_path: Path,
) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    target = root / "restart-notes.txt"
    target.write_text("restart wal recovery checklist\n", encoding="utf-8")

    source = tmp_path / "source.db"
    snapshot = tmp_path / "snapshot.db"

    conn = open_index(source)
    try:
        conn.execute("PRAGMA wal_autocheckpoint=0;")
        conn.execute(
            "INSERT INTO roots(id, path, include, exclude, added_at) VALUES (?, ?, ?, ?, ?)",
            (1, str(root), "[]", "[]", 1),
        )
        conn.commit()
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        rules = PathRules(root=root, include=(str(root), f"{root}/**"), exclude=())
        records = [record for batch in walk_batched(root, rules, root_id=1) for record in batch]
        assert writer.bulk_upsert(records) == len(records)

        shutil.copy2(source, snapshot)
        shutil.copy2(source.with_name("source.db-wal"), snapshot.with_name("snapshot.db-wal"))
        shutil.copy2(source.with_name("source.db-shm"), snapshot.with_name("snapshot.db-shm"))
    finally:
        conn.close()

    assert has_stale_wal(snapshot)

    first_search = cli_runner("--db", str(snapshot), "search", "restart wal recovery", "--json")
    second_search = cli_runner("--db", str(snapshot), "search", "restart wal recovery", "--json")

    assert first_search.returncode == 0
    assert second_search.returncode == 0
    assert _result_names(json.loads(first_search.stdout)) == ["restart-notes.txt"]
    assert _result_names(json.loads(second_search.stdout)) == ["restart-notes.txt"]
    for suffix in ("-wal", "-shm"):
        assert not snapshot.with_name(f"{snapshot.name}{suffix}").exists()
