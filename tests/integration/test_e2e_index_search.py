from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
from queue import Empty

import pytest
from watchdog.events import FileMovedEvent

from eodinga.common import PathRules, WatchEvent
from eodinga.content.registry import parse
from eodinga.core.watcher import WatchService, _Handler
from eodinga.index import open_index
from eodinga.index.writer import IndexWriter
from eodinga.core.walker import walk_batched
from eodinga.query import search
from tests.conftest import make_record


def _build_fixture_tree(root: Path) -> None:
    local_now = datetime.now().astimezone()
    today = local_now.replace(hour=12, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)
    files = {
        "docs/launch-plan.md": "# Launch Plan\nAlpha launch checklist for spring release.\n",
        "docs/invoice-budget.txt": "Invoice budget for the alpha launch.\n",
        "archive/retro-notes.txt": "Archive retrospective notes from last quarter.\n",
        "src/hot_restart.py": "def reopen_index():\n    return 'restart ready'\n",
        "src/watch_coalesce.py": "EVENT_NAME = 'coalesce'\n",
        "korean/회의록-봄.txt": "봄 프로젝트 회의록과 실행 항목.\n",
        "korean/영수증-정산.txt": "정산 영수증과 비용 내역.\n",
        "reports/today-alpha-copy.txt": "alpha duplicate launch note\n",
        "reports/today-alpha-clone.txt": "alpha duplicate launch note\n",
        "archive/yesterday-beta.txt": "beta archive note\n",
    }
    for relative_path, body in files.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    large_paths = [
        root / "reports" / "today-alpha-copy.txt",
        root / "reports" / "today-alpha-clone.txt",
        root / "archive" / "yesterday-beta.txt",
    ]
    sizes = [12 * 1024 * 1024, 11 * 1024 * 1024, 9 * 1024 * 1024]
    mtimes = [today.timestamp(), today.timestamp() + 60, yesterday.timestamp()]
    for path, size, mtime in zip(large_paths, sizes, mtimes, strict=True):
        with path.open("ab") as handle:
            handle.truncate(size)
        os.utime(path, (mtime, mtime))


def _index_tree(root: Path, db_path: Path) -> None:
    conn = open_index(db_path)
    try:
        conn.execute(
            "INSERT INTO roots(id, path, include, exclude, added_at) VALUES (?, ?, ?, ?, ?)",
            (1, str(root), "[]", "[]", 1),
        )
        conn.commit()
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=4096))
        rules = PathRules(root=root, include=(str(root), f"{root}/**"), exclude=())
        records = [
            record
            for batch in walk_batched(root, rules, root_id=1)
            for record in batch
        ]
        assert writer.bulk_upsert(records) == len(records)
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("query", "expected_name"),
    [
        ("launch-plan", "launch-plan.md"),
        ('content:"launch checklist"', "launch-plan.md"),
        ("ext:md launch", "launch-plan.md"),
        ("path:archive retro", "retro-notes.txt"),
        ("path:src reopen_index", "hot_restart.py"),
        ("content:/coalesce/i", "watch_coalesce.py"),
        ("회의록", "회의록-봄.txt"),
        ("content:정산", "영수증-정산.txt"),
        ("path:korean 영수증", "영수증-정산.txt"),
        ("invoice budget", "invoice-budget.txt"),
        ("date:today size:>10M is:duplicate -path:archive", "today-alpha-copy.txt"),
        ("date:yesterday -is:duplicate", "yesterday-beta.txt"),
    ],
)
def test_e2e_index_search_returns_expected_file_in_top_three(
    tmp_path: Path, query: str, expected_name: str
) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    _build_fixture_tree(root)
    _index_tree(root, db_path)

    conn = open_index(db_path)
    try:
        hits = [hit.file.name for hit in search(conn, query, limit=3).hits]
    finally:
        conn.close()

    assert expected_name in hits


def test_e2e_index_search_accepts_short_slash_prefixed_path_literals(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    _build_fixture_tree(root)
    short_path = root / "tmp" / "log"
    short_path.parent.mkdir(parents=True, exist_ok=True)
    short_path.write_text("short path literal\n", encoding="utf-8")
    _index_tree(root, db_path)

    conn = open_index(db_path)
    try:
        hits = [hit.file.path for hit in search(conn, f"path:{short_path}", limit=3).hits]
    finally:
        conn.close()

    assert hits == [short_path]


def test_e2e_index_search_supports_iso_month_and_year_periods(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    _build_fixture_tree(root)
    april_file = root / "reports" / "period-april.txt"
    june_file = root / "reports" / "period-june.txt"
    prior_year_file = root / "archive" / "period-previous-year.txt"
    april_file.write_text("period april note\n", encoding="utf-8")
    june_file.write_text("period june note\n", encoding="utf-8")
    prior_year_file.write_text("period previous year note\n", encoding="utf-8")
    dated_paths = [
        (april_file, datetime(2026, 4, 15, 12, 0).astimezone().timestamp()),
        (june_file, datetime(2026, 6, 15, 12, 0).astimezone().timestamp()),
        (prior_year_file, datetime(2025, 12, 15, 12, 0).astimezone().timestamp()),
    ]
    for path, stamp in dated_paths:
        os.utime(path, (stamp, stamp))
    _index_tree(root, db_path)

    conn = open_index(db_path)
    try:
        april_hits = [hit.file.name for hit in search(conn, "period date:2026-04", limit=5).hits]
        year_hits = [hit.file.name for hit in search(conn, "period date:2026", limit=5).hits]
    finally:
        conn.close()

    assert april_hits == ["period-april.txt"]
    assert set(year_hits) >= {"period-april.txt", "period-june.txt"}
    assert "period-previous-year.txt" not in year_hits


def test_e2e_index_search_preserves_symlink_root_alias_paths(tmp_path: Path) -> None:
    real_root = tmp_path / "workspace-real"
    alias_root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    _build_fixture_tree(real_root)
    alias_root.symlink_to(real_root, target_is_directory=True)
    _index_tree(alias_root, db_path)

    conn = open_index(db_path)
    try:
        hit = search(conn, "회의록", limit=1).hits[0]
        indexed_paths = {
            Path(row[0])
            for row in conn.execute("SELECT path FROM files").fetchall()
        }
    finally:
        conn.close()

    assert hit.file.path == alias_root / "korean" / "회의록-봄.txt"
    assert alias_root in indexed_paths
    assert all(str(path).startswith(str(alias_root)) for path in indexed_paths)


def test_e2e_plain_negated_term_filters_auto_content_hits(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    root.mkdir()
    (root / "alpha.txt").write_text("note launch\n", encoding="utf-8")
    (root / "beta.txt").write_text("note archive\n", encoding="utf-8")
    (root / "gamma.txt").write_text("archive only\n", encoding="utf-8")
    _index_tree(root, db_path)

    conn = open_index(db_path)
    try:
        hits = [hit.file.name for hit in search(conn, "note -launch", limit=5).hits]
    finally:
        conn.close()

    assert hits == ["beta.txt"]


def test_e2e_watch_move_then_recreate_delete_does_not_leave_ghost_source(tmp_path: Path) -> None:
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

        source.rename(backup)
        source.write_text("replacement body\n", encoding="utf-8")
        source.unlink()

        service = WatchService()
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

        indexed_paths = {
            Path(row[0])
            for row in conn.execute("SELECT path FROM files WHERE is_dir = 0").fetchall()
        }
    finally:
        conn.close()

    assert indexed_paths == {backup}


def test_e2e_watch_flushed_move_then_late_source_delete_keeps_destination(tmp_path: Path) -> None:
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

        service.record(
            WatchEvent(
                event_type="moved",
                path=backup,
                src_path=source,
                root_path=root,
                happened_at=1.0,
            )
        )
        service._flush_ready(force=True)

        moved_event = service.queue.get_nowait()
        assert moved_event.event_type == "moved"
        assert writer.apply_events([moved_event], record_loader=make_record) == 1

        service.record(
            WatchEvent(
                event_type="deleted",
                path=source,
                root_path=root,
                happened_at=2.0,
            )
        )
        service._flush_ready(force=True)

        with pytest.raises(Empty):
            service.queue.get_nowait()

        indexed_paths = {
            Path(row[0])
            for row in conn.execute("SELECT path FROM files WHERE is_dir = 0").fetchall()
        }
    finally:
        conn.close()

    assert indexed_paths == {backup}


def test_e2e_watch_move_then_destination_create_deletes_source_row(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    root.mkdir()
    source = root / "draft.txt"
    destination = root / "report.txt"
    source.write_text("draft body\n", encoding="utf-8")
    _index_tree(root, db_path)

    conn = open_index(db_path)
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))

        source.rename(destination)
        service = WatchService()
        service.record(
            WatchEvent(
                event_type="moved",
                path=destination,
                src_path=source,
                root_path=root,
                happened_at=1.0,
            )
        )
        service.record(
            WatchEvent(
                event_type="created",
                path=destination,
                root_path=root,
                happened_at=2.0,
            )
        )
        service._flush_ready(force=True)

        events = []
        while not service.queue.empty():
            events.append(service.queue.get_nowait())

        assert [(event.event_type, event.path.name) for event in events] == [("moved", "report.txt")]
        assert writer.apply_events(events, record_loader=make_record) == 1

        indexed_paths = {
            Path(row[0])
            for row in conn.execute("SELECT path FROM files WHERE is_dir = 0 ORDER BY path").fetchall()
        }
    finally:
        conn.close()

    assert indexed_paths == {destination}


def test_e2e_watch_handler_move_leaving_root_deletes_indexed_row(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    outside = tmp_path / "outside"
    db_path = tmp_path / "database" / "index.db"
    root.mkdir()
    outside.mkdir()
    source = root / "draft.txt"
    destination = outside / "draft.txt"
    source.write_text("draft body\n", encoding="utf-8")
    _index_tree(root, db_path)

    conn = open_index(db_path)
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        handler = _Handler(WatchService(), root)

        source.rename(destination)
        handler.on_any_event(FileMovedEvent(str(source), str(destination)))
        handler._service._flush_ready(force=True)

        event = handler._service.queue.get_nowait()
        assert event.event_type == "deleted"
        assert writer.apply_events([event], record_loader=make_record) == 1

        indexed_paths = {
            Path(row[0])
            for row in conn.execute("SELECT path FROM files WHERE is_dir = 0").fetchall()
        }
    finally:
        conn.close()

    assert indexed_paths == set()


def test_e2e_watch_handler_move_entering_root_creates_indexed_row(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    outside = tmp_path / "outside"
    db_path = tmp_path / "database" / "index.db"
    root.mkdir()
    outside.mkdir()
    source = outside / "draft.txt"
    destination = root / "draft.txt"
    source.write_text("draft body\n", encoding="utf-8")
    _index_tree(root, db_path)

    conn = open_index(db_path)
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        handler = _Handler(WatchService(), root)

        source.rename(destination)
        handler.on_any_event(FileMovedEvent(str(source), str(destination)))
        handler._service._flush_ready(force=True)

        event = handler._service.queue.get_nowait()
        assert event.event_type == "created"
        assert writer.apply_events([event], record_loader=make_record) == 1

        indexed_paths = {
            Path(row[0])
            for row in conn.execute("SELECT path FROM files WHERE is_dir = 0").fetchall()
        }
    finally:
        conn.close()

    assert indexed_paths == {destination}
