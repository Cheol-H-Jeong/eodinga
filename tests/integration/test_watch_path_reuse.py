from __future__ import annotations

from pathlib import Path

from eodinga.common import PathRules, WatchEvent
from eodinga.content.registry import parse
from eodinga.core.walker import walk_batched
from eodinga.core.watcher import WatchService
from eodinga.index import open_index
from eodinga.index.writer import IndexWriter
from eodinga.query import search
from tests.conftest import make_record


def _index_tree(root: Path, db_path: Path) -> None:
    conn = open_index(db_path)
    try:
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


def test_e2e_move_then_recreate_delete_keeps_destination_and_no_ghost_source(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    root.mkdir()
    source = root / "draft.txt"
    backup = root / "draft.bak"
    source.write_text("draft body\n", encoding="utf-8")
    _index_tree(root, db_path)

    conn = open_index(db_path)
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service = WatchService()

        source.rename(backup)
        source.write_text("replacement body\n", encoding="utf-8")
        source.unlink()

        service.record(
            WatchEvent(
                event_type="moved",
                path=backup,
                src_path=source,
                root_path=root,
                happened_at=1.0,
            )
        )
        service.record(
            WatchEvent(
                event_type="created",
                path=source,
                root_path=root,
                happened_at=2.0,
            )
        )
        service.record(
            WatchEvent(
                event_type="deleted",
                path=source,
                root_path=root,
                happened_at=3.0,
            )
        )
        service._flush_ready(force=True)

        events = []
        while not service.queue.empty():
            events.append(service.queue.get_nowait())

        assert [event.event_type for event in events] == ["moved"]
        assert writer.apply_events(events, record_loader=make_record) == 1

        backup_hits = [hit.file.path for hit in search(conn, "path:draft.bak", limit=5).hits]
        source_hits = [hit.file.path for hit in search(conn, "replacement body", limit=5).hits]
        indexed_paths = {
            Path(row[0]) for row in conn.execute("SELECT path FROM files WHERE is_dir = 0").fetchall()
        }
    finally:
        conn.close()

    assert backup_hits == [backup]
    assert source_hits == []
    assert indexed_paths == {backup}


def test_e2e_move_then_reused_source_modify_delete_keeps_real_delete(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    root.mkdir()
    source = root / "draft.txt"
    backup = root / "draft.bak"
    source.write_text("draft body\n", encoding="utf-8")
    _index_tree(root, db_path)

    conn = open_index(db_path)
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service = WatchService()

        source.rename(backup)
        source.write_text("replacement body\n", encoding="utf-8")
        source.write_text("replacement body updated\n", encoding="utf-8")
        source.unlink()

        service.record(
            WatchEvent(
                event_type="moved",
                path=backup,
                src_path=source,
                root_path=root,
                happened_at=1.0,
            )
        )
        service.record(
            WatchEvent(
                event_type="modified",
                path=source,
                root_path=root,
                happened_at=2.0,
            )
        )
        service.record(
            WatchEvent(
                event_type="deleted",
                path=source,
                root_path=root,
                happened_at=3.0,
            )
        )
        service._flush_ready(force=True)

        events = []
        while not service.queue.empty():
            events.append(service.queue.get_nowait())

        assert [event.event_type for event in events] == ["moved", "deleted"]
        assert writer.apply_events(events, record_loader=make_record) == 2

        backup_hits = [hit.file.path for hit in search(conn, "path:draft.bak", limit=5).hits]
        source_hits = [hit.file.path for hit in search(conn, "replacement body updated", limit=5).hits]
        indexed_paths = {
            Path(row[0]) for row in conn.execute("SELECT path FROM files WHERE is_dir = 0").fetchall()
        }
    finally:
        conn.close()

    assert backup_hits == [backup]
    assert source_hits == []
    assert indexed_paths == {backup}
