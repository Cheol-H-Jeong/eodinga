from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, cast

from eodinga.__main__ import main
from eodinga.common import PathRules
from eodinga.content.registry import parse
from eodinga.index.storage import open_index
from eodinga.index.writer import IndexWriter
from eodinga.core.walker import walk_batched


def _read_json(capsys) -> dict[str, Any]:
    captured = capsys.readouterr()
    return cast(dict[str, Any], json.loads(captured.out))


def _seed_index_with_root(db_path: Path, root: Path) -> None:
    conn = open_index(db_path)
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
    finally:
        conn.close()


def test_cli_search_recovers_stale_wal_before_querying(tmp_path: Path, capsys) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "restart-note.txt").write_text("cli stale wal recovery\n", encoding="utf-8")
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

    assert main(["--db", str(snapshot), "search", "stale wal recovery", "--json"]) == 0
    payload = _read_json(capsys)
    results = cast(list[dict[str, Any]], payload["results"])

    assert [Path(cast(str, item["path"])).name for item in results] == ["restart-note.txt"]
    assert not snapshot.with_name("snapshot.db-wal").exists()
    assert not snapshot.with_name("snapshot.db-shm").exists()


def test_cli_search_resumes_interrupted_staged_build_before_querying(tmp_path: Path, capsys) -> None:
    root = tmp_path / "workspace"
    db_dir = tmp_path / "database"
    target_db = db_dir / "index.db"
    staged_db = db_dir / ".index.db.next"
    root.mkdir()
    db_dir.mkdir()
    (root / "resumed.txt").write_text("cli staged build recovery\n", encoding="utf-8")

    _seed_index_with_root(staged_db, root)

    assert not target_db.exists()
    assert staged_db.exists()

    assert main(["--db", str(target_db), "search", "staged build recovery", "--json"]) == 0
    payload = _read_json(capsys)
    results = cast(list[dict[str, Any]], payload["results"])

    assert [Path(cast(str, item["path"])).name for item in results] == ["resumed.txt"]
    assert target_db.exists()
    assert not staged_db.exists()
