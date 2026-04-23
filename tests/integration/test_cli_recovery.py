from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, cast

from eodinga.__main__ import main
from eodinga.common import PathRules
from eodinga.config import RootConfig
from eodinga.content.registry import parse
from eodinga.core.walker import walk_batched
from eodinga.index.build import rebuild_index
from eodinga.index.storage import has_stale_wal, open_index
from eodinga.index.writer import IndexWriter


def _run_json(capsys, *args: str) -> tuple[dict[str, Any], str]:
    exit_code = main(list(args))
    captured = capsys.readouterr()
    assert exit_code == 0
    payload = cast(dict[str, Any], json.loads(captured.out))
    return payload, captured.err


def _seed_index(db_path: Path, root: Path) -> None:
    conn = open_index(db_path)
    try:
        conn.execute(
            "INSERT INTO roots(id, path, include, exclude, added_at) VALUES (?, ?, ?, ?, ?)",
            (1, str(root), "[]", "[]", 1),
        )
        conn.commit()
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        rules = PathRules(root=root, include=(str(root), f"{root}/**"), exclude=())
        records = [
            record
            for batch in walk_batched(root, rules, root_id=1)
            for record in batch
        ]
        assert writer.bulk_upsert(records) == len(records)
    finally:
        conn.close()


def test_cli_search_recovers_stale_wal_before_querying(tmp_path: Path, capsys) -> None:
    root = tmp_path / "workspace"
    source_db = tmp_path / "source.db"
    snapshot_db = tmp_path / "snapshot.db"
    root.mkdir()
    target = root / "restart-notes.txt"
    target.write_text("restart recovery checklist\n", encoding="utf-8")

    conn = open_index(source_db)
    try:
        conn.execute("PRAGMA wal_autocheckpoint=0;")
        conn.execute(
            "INSERT INTO roots(id, path, include, exclude, added_at) VALUES (?, ?, ?, ?, ?)",
            (1, str(root), "[]", "[]", 1),
        )
        conn.commit()
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        rules = PathRules(root=root, include=(str(root), f"{root}/**"), exclude=())
        records = [
            record
            for batch in walk_batched(root, rules, root_id=1)
            for record in batch
        ]
        assert writer.bulk_upsert(records) == len(records)

        shutil.copy2(source_db, snapshot_db)
        shutil.copy2(source_db.with_name("source.db-wal"), snapshot_db.with_name("snapshot.db-wal"))
        shutil.copy2(source_db.with_name("source.db-shm"), snapshot_db.with_name("snapshot.db-shm"))
    finally:
        conn.close()

    assert has_stale_wal(snapshot_db)

    payload, stderr = _run_json(
        capsys,
        "--db",
        str(snapshot_db),
        "search",
        "restart recovery",
        "--json",
    )

    assert "recovering stale WAL" in stderr
    assert [Path(item["path"]) for item in cast(list[dict[str, Any]], payload["results"])] == [target]
    for suffix in ("-wal", "-shm"):
        assert not snapshot_db.with_name(f"{snapshot_db.name}{suffix}").exists()


def test_cli_search_resumes_interrupted_staged_build_before_querying(tmp_path: Path, capsys) -> None:
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

    payload, stderr = _run_json(
        capsys,
        "--db",
        str(target_db),
        "search",
        "staged build recovery",
        "--json",
    )

    assert "resuming interrupted staged build" in stderr
    assert [Path(item["path"]) for item in cast(list[dict[str, Any]], payload["results"])] == [existing]
    assert not staged_db.exists()
