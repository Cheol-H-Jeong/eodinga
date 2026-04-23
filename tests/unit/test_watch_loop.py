from __future__ import annotations

import sqlite3
from pathlib import Path

from eodinga.common import WatchEvent
from eodinga.config import RootConfig
from eodinga.core.watcher import WatchService
from eodinga.index.schema import apply_schema
from eodinga.watch_loop import WatchRoot, load_watch_roots, make_record_loader
from eodinga.common import PathRules


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    apply_schema(conn)
    return conn


def test_load_watch_roots_falls_back_to_config_and_persists_roots(tmp_path: Path) -> None:
    db_path = tmp_path / "index.db"
    root = tmp_path / "workspace"
    root.mkdir()
    config_roots = [RootConfig(path=root)]

    conn = _connect(db_path)
    try:
        roots = load_watch_roots(conn, config_roots)
        stored = conn.execute("SELECT id, path FROM roots ORDER BY id").fetchall()
    finally:
        conn.close()

    assert [watch_root.path for watch_root in roots] == [root]
    assert [(int(row["id"]), Path(row["path"])) for row in stored] == [(1, root)]


def test_load_watch_roots_prefers_index_roots_over_config(tmp_path: Path) -> None:
    db_path = tmp_path / "index.db"
    indexed_root = tmp_path / "indexed"
    config_root = tmp_path / "config"
    indexed_root.mkdir()
    config_root.mkdir()

    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT INTO roots(id, path, include, exclude, enabled, added_at) VALUES (?, ?, ?, ?, ?, ?)",
            (7, str(indexed_root), '["**/*"]', "[]", 1, 1),
        )
        conn.commit()

        roots = load_watch_roots(conn, [RootConfig(path=config_root)])
    finally:
        conn.close()

    assert [(root.id, root.path) for root in roots] == [(7, indexed_root)]


def test_make_record_loader_uses_deepest_matching_root_and_respects_rules(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    nested = root / "nested"
    root.mkdir()
    nested.mkdir()
    allowed = nested / "keep.txt"
    blocked = nested / "skip.tmp"
    allowed.write_text("keep\n", encoding="utf-8")
    blocked.write_text("skip\n", encoding="utf-8")

    loader = make_record_loader(
        [
            WatchRoot(id=1, path=root, rules=PathRules(root=root, include=("**/*",), exclude=())),
            WatchRoot(
                id=2,
                path=nested,
                rules=PathRules(root=nested, include=("**/*",), exclude=("**/*.tmp",)),
            ),
        ]
    )

    allowed_record = loader(allowed)
    blocked_record = loader(blocked)

    assert allowed_record is not None
    assert allowed_record.root_id == 2
    assert blocked_record is None


def test_watch_service_stop_can_preserve_flushed_queue(tmp_path: Path) -> None:
    service = WatchService()
    path = tmp_path / "queued.txt"
    service.record(
        WatchEvent(
            event_type="created",
            path=path,
            root_path=tmp_path,
            happened_at=1.0,
        )
    )
    service._flush_ready(force=True)

    service.stop(clear_queue=False)

    queued = service.queue.get_nowait()
    assert queued.path == path
