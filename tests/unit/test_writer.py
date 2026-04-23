from __future__ import annotations

import sqlite3
from pathlib import Path
from time import perf_counter, time

import eodinga.index.writer as writer_module
from eodinga.content.base import ParsedContent
from eodinga.common import FileRecord, WatchEvent
from eodinga.index.writer import IndexWriter
from tests.conftest import make_record


def _synthetic_record(index: int, root: Path) -> FileRecord:
    path = root / f"file-{index}.txt"
    return FileRecord(
        root_id=1,
        path=path,
        parent_path=root,
        name=path.name,
        name_lower=path.name.lower(),
        ext="txt",
        size=index,
        mtime=1,
        ctime=1,
        is_dir=False,
        is_symlink=False,
        indexed_at=int(time()),
    )


def test_writer_bulk_insert_and_incremental_apply_are_fast(tmp_db: Path, tmp_path: Path) -> None:
    conn = sqlite3.connect(tmp_db)
    conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        (str(tmp_path), "[]", "[]", 1),
    )
    writer = IndexWriter(conn)
    records = [_synthetic_record(index, tmp_path) for index in range(5000)]

    started = perf_counter()
    assert writer.bulk_upsert(records) == 5000
    bulk_elapsed = perf_counter() - started
    assert bulk_elapsed < 2.0

    files: list[Path] = []
    for index in range(100):
        path = tmp_path / f"live-{index}.txt"
        path.write_text("live", encoding="utf-8")
        files.append(path)
    events = [WatchEvent(event_type="created", path=path) for path in files]

    started = perf_counter()
    processed = writer.apply_events(events, record_loader=lambda path: make_record(path))
    incr_elapsed = perf_counter() - started
    assert processed == 100
    assert incr_elapsed < 0.05


def test_writer_caches_chunk_shaped_sql_templates() -> None:
    writer_module._delete_files_sql.cache_clear()
    writer_module._delete_content_rows_sql.cache_clear()
    writer_module._select_deleted_content_rowids_sql.cache_clear()
    writer_module._select_existing_content_rows_sql.cache_clear()

    writer_module._delete_files_sql(2)
    writer_module._delete_files_sql(2)
    writer_module._delete_content_rows_sql(3)
    writer_module._delete_content_rows_sql(3)
    writer_module._select_deleted_content_rowids_sql(4)
    writer_module._select_deleted_content_rowids_sql(4)
    writer_module._select_existing_content_rows_sql(5)
    writer_module._select_existing_content_rows_sql(5)

    assert writer_module._delete_files_sql.cache_info().hits >= 1
    assert writer_module._delete_content_rows_sql.cache_info().hits >= 1
    assert writer_module._select_deleted_content_rowids_sql.cache_info().hits >= 1
    assert writer_module._select_existing_content_rows_sql.cache_info().hits >= 1


def test_writer_without_parser_skips_content_queries(tmp_db: Path, tmp_path: Path) -> None:
    conn = sqlite3.connect(tmp_db)
    conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        (str(tmp_path), "[]", "[]", 1),
    )
    records = [_synthetic_record(index, tmp_path) for index in range(3)]
    writer = IndexWriter(conn)

    statements: list[str] = []
    conn.set_trace_callback(statements.append)
    try:
        assert writer.bulk_upsert(records) == 3
    finally:
        conn.set_trace_callback(None)

    assert not any("content_map" in statement for statement in statements)
    assert conn.execute("SELECT COUNT(*) FROM content_map").fetchone() == (0,)


def test_writer_bulk_upsert_batches_content_inserts(tmp_db: Path, tmp_path: Path) -> None:
    conn = sqlite3.connect(tmp_db)
    conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        (str(tmp_path), "[]", "[]", 1),
    )
    records = [_synthetic_record(index, tmp_path) for index in range(3)]
    parsed_by_path = {
        record.path: ParsedContent(
            title=record.name,
            head_text=f"head {record.name}",
            body_text=f"body {record.name}",
            content_sha=f"sha-{record.name}".encode(),
        )
        for record in records
    }
    writer = IndexWriter(conn, parser_callback=lambda path: parsed_by_path.get(path))

    assert writer.bulk_upsert(records) == 3

    rows = conn.execute(
        """
        SELECT files.name, content_fts.title, content_fts.body_text, content_map.content_sha
        FROM files
        JOIN content_map ON content_map.file_id = files.id
        JOIN content_fts ON content_fts.rowid = content_map.fts_rowid
        ORDER BY files.name
        """
    ).fetchall()
    assert len(rows) == 3
    assert rows[0] == (
        "file-0.txt",
        "file-0.txt",
        "body file-0.txt",
        b"sha-file-0.txt",
    )
    hashes = conn.execute("SELECT name, content_hash FROM files ORDER BY name").fetchall()
    assert hashes[0] == ("file-0.txt", b"sha-file-0.txt")


def test_writer_bulk_upsert_parses_duplicate_paths_once(tmp_db: Path, tmp_path: Path) -> None:
    conn = sqlite3.connect(tmp_db)
    conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        (str(tmp_path), "[]", "[]", 1),
    )
    record = _synthetic_record(1, tmp_path)
    calls: list[Path] = []

    def parse_once(path: Path) -> ParsedContent:
        calls.append(path)
        return ParsedContent(
            title=path.name,
            head_text=f"head {path.name}",
            body_text=f"body {path.name}",
            content_sha=f"sha-{path.name}".encode(),
        )

    writer = IndexWriter(conn, parser_callback=parse_once)

    assert writer.bulk_upsert([record, record, record]) == 3
    assert calls == [record.path]
    rows = conn.execute("SELECT COUNT(*), MIN(content_hash) FROM files").fetchone()
    assert rows == (1, b"sha-file-1.txt")


def test_writer_apply_events_batches_deleted_path_cleanup(tmp_db: Path, tmp_path: Path) -> None:
    conn = sqlite3.connect(tmp_db)
    conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        (str(tmp_path), "[]", "[]", 1),
    )
    records = [_synthetic_record(index, tmp_path) for index in range(3)]
    parsed_by_path = {
        record.path: ParsedContent(
            title=record.name,
            head_text=f"head {record.name}",
            body_text=f"body {record.name}",
            content_sha=f"sha-{record.name}".encode(),
        )
        for record in records
    }
    writer = IndexWriter(conn, parser_callback=lambda path: parsed_by_path.get(path))
    assert writer.bulk_upsert(records) == 3

    statements: list[str] = []
    conn.set_trace_callback(statements.append)
    try:
        processed = writer.apply_events(
            [
                WatchEvent(event_type="deleted", path=records[0].path),
                WatchEvent(event_type="deleted", path=records[1].path),
            ],
            record_loader=lambda _path: None,
        )
    finally:
        conn.set_trace_callback(None)

    assert processed == 2
    batched_selects = {
        statement.strip()
        for statement in statements
        if "SELECT content_map.fts_rowid" in statement and "WHERE files.path IN" in statement
    }
    batched_deletes = {
        statement.strip() for statement in statements if statement.startswith("DELETE FROM files WHERE path IN")
    }
    assert len(batched_selects) == 1
    assert len(batched_deletes) == 1
    assert conn.execute("SELECT COUNT(*) FROM files").fetchone() == (1,)
    assert conn.execute("SELECT COUNT(*) FROM content_fts").fetchone() == (1,)


def test_writer_apply_events_batches_moved_source_cleanup(tmp_db: Path, tmp_path: Path) -> None:
    conn = sqlite3.connect(tmp_db)
    conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        (str(tmp_path), "[]", "[]", 1),
    )
    records = [_synthetic_record(index, tmp_path) for index in range(2)]
    writer = IndexWriter(conn)
    assert writer.bulk_upsert(records) == 2

    moved_paths = [tmp_path / "moved-0.txt", tmp_path / "moved-1.txt"]
    for index, path in enumerate(moved_paths):
        path.write_text(f"moved {index}", encoding="utf-8")

    statements: list[str] = []
    conn.set_trace_callback(statements.append)
    try:
        processed = writer.apply_events(
            [
                WatchEvent(event_type="moved", src_path=records[0].path, path=moved_paths[0]),
                WatchEvent(event_type="moved", src_path=records[1].path, path=moved_paths[1]),
            ],
            record_loader=make_record,
        )
    finally:
        conn.set_trace_callback(None)

    assert processed == 2
    batched_selects = {
        statement.strip()
        for statement in statements
        if "SELECT content_map.fts_rowid" in statement and "WHERE files.path IN" in statement
    }
    batched_deletes = {
        statement.strip() for statement in statements if statement.startswith("DELETE FROM files WHERE path IN")
    }
    assert len(batched_selects) == 1
    assert len(batched_deletes) == 1
    remaining_paths = {
        row[0] for row in conn.execute("SELECT path FROM files ORDER BY path").fetchall()
    }
    assert remaining_paths == {str(path) for path in moved_paths}


def test_writer_bulk_upsert_reuses_existing_content_rowids(tmp_db: Path, tmp_path: Path) -> None:
    conn = sqlite3.connect(tmp_db)
    conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        (str(tmp_path), "[]", "[]", 1),
    )
    record = _synthetic_record(1, tmp_path)
    initial = ParsedContent(
        title=record.name,
        head_text="head one",
        body_text="body one",
        content_sha=b"sha-one",
    )
    updated = ParsedContent(
        title=record.name,
        head_text="head two",
        body_text="body two",
        content_sha=b"sha-two",
    )

    writer = IndexWriter(conn, parser_callback=lambda _path: initial)
    assert writer.bulk_upsert([record]) == 1
    before = conn.execute("SELECT fts_rowid, content_sha FROM content_map").fetchone()

    writer = IndexWriter(conn, parser_callback=lambda _path: updated)
    assert writer.bulk_upsert([record]) == 1
    after = conn.execute(
        """
        SELECT content_map.fts_rowid, content_map.content_sha, content_fts.body_text
        FROM content_map
        JOIN content_fts ON content_fts.rowid = content_map.fts_rowid
        """
    ).fetchone()

    assert before is not None
    assert after is not None
    assert after[0] == before[0]
    assert after[1] == b"sha-two"
    assert after[2] == "body two"
    file_hash = conn.execute("SELECT content_hash FROM files WHERE path = ?", (str(record.path),)).fetchone()
    assert file_hash == (b"sha-two",)


def test_writer_bulk_upsert_skips_unchanged_content_rewrite(tmp_db: Path, tmp_path: Path) -> None:
    conn = sqlite3.connect(tmp_db)
    conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        (str(tmp_path), "[]", "[]", 1),
    )
    record = _synthetic_record(1, tmp_path)
    parsed = ParsedContent(
        title=record.name,
        head_text="head stable",
        body_text="body stable",
        content_sha=b"sha-stable",
    )

    writer = IndexWriter(conn, parser_callback=lambda _path: parsed)
    assert writer.bulk_upsert([record]) == 1
    before = conn.execute(
        """
        SELECT content_map.fts_rowid, content_map.content_sha, content_fts.body_text
        FROM content_map
        JOIN content_fts ON content_fts.rowid = content_map.fts_rowid
        """
    ).fetchone()

    statements: list[str] = []
    conn.set_trace_callback(statements.append)
    try:
        assert writer.bulk_upsert([record]) == 1
    finally:
        conn.set_trace_callback(None)

    after = conn.execute(
        """
        SELECT content_map.fts_rowid, content_map.content_sha, content_fts.body_text
        FROM content_map
        JOIN content_fts ON content_fts.rowid = content_map.fts_rowid
        """
    ).fetchone()

    assert before == after
    assert not any("DELETE FROM content_fts" in statement for statement in statements)
    assert not any("INSERT INTO content_fts" in statement for statement in statements)


def test_writer_bulk_upsert_skips_next_rowid_probe_for_unchanged_content(
    tmp_db: Path, tmp_path: Path
) -> None:
    conn = sqlite3.connect(tmp_db)
    conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        (str(tmp_path), "[]", "[]", 1),
    )
    record = _synthetic_record(1, tmp_path)
    parsed = ParsedContent(
        title=record.name,
        head_text="head stable",
        body_text="body stable",
        content_sha=b"sha-stable",
    )

    writer = IndexWriter(conn, parser_callback=lambda _path: parsed)
    assert writer.bulk_upsert([record]) == 1

    statements: list[str] = []
    conn.set_trace_callback(statements.append)
    try:
        assert writer.bulk_upsert((record,)) == 1
    finally:
        conn.set_trace_callback(None)

    assert not any("SELECT COALESCE(MAX(rowid), 0) + 1 FROM content_fts" in statement for statement in statements)


def test_writer_bulk_upsert_reuses_cached_next_rowid_across_batches(
    tmp_db: Path, tmp_path: Path
) -> None:
    conn = sqlite3.connect(tmp_db)
    conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        (str(tmp_path), "[]", "[]", 1),
    )
    first = _synthetic_record(1, tmp_path)
    second = _synthetic_record(2, tmp_path)

    def parsed_for(path: Path) -> ParsedContent:
        return ParsedContent(
            title=path.name,
            head_text=f"head {path.name}",
            body_text=f"body {path.name}",
            content_sha=f"sha-{path.name}".encode(),
        )

    writer = IndexWriter(conn, parser_callback=parsed_for)
    assert writer.bulk_upsert([first]) == 1

    statements: list[str] = []
    conn.set_trace_callback(statements.append)
    try:
        assert writer.bulk_upsert([second]) == 1
    finally:
        conn.set_trace_callback(None)

    assert not any("SELECT COALESCE(MAX(rowid), 0) + 1 FROM content_fts" in statement for statement in statements)
    rowids = conn.execute("SELECT fts_rowid FROM content_map ORDER BY file_id").fetchall()
    assert rowids == [(1,), (2,)]


def test_writer_bulk_upsert_preserves_existing_content_hash_when_record_has_none(
    tmp_db: Path, tmp_path: Path
) -> None:
    conn = sqlite3.connect(tmp_db)
    conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        (str(tmp_path), "[]", "[]", 1),
    )
    record = _synthetic_record(1, tmp_path)
    parsed = ParsedContent(
        title=record.name,
        head_text="head one",
        body_text="body one",
        content_sha=b"sha-one",
    )

    writer = IndexWriter(conn, parser_callback=lambda _path: parsed)
    assert writer.bulk_upsert([record]) == 1

    # Plain record upserts should not clear a persisted content hash before the parser runs.
    writer._upsert_records([record])

    file_hash = conn.execute("SELECT content_hash FROM files WHERE path = ?", (str(record.path),)).fetchone()
    assert file_hash == (b"sha-one",)


def test_writer_clears_file_content_hash_for_empty_parsed_content(tmp_db: Path, tmp_path: Path) -> None:
    conn = sqlite3.connect(tmp_db)
    conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        (str(tmp_path), "[]", "[]", 1),
    )
    record = _synthetic_record(1, tmp_path)
    parsed = ParsedContent(
        title=record.name,
        head_text="",
        body_text="",
        content_sha=b"",
    )
    writer = IndexWriter(conn, parser_callback=lambda _path: parsed)

    assert writer.bulk_upsert([record]) == 1

    file_hash = conn.execute("SELECT content_hash FROM files WHERE path = ?", (str(record.path),)).fetchone()
    assert file_hash == (None,)


def test_writer_bulk_upsert_respects_active_transaction_rollback(tmp_db: Path, tmp_path: Path) -> None:
    conn = sqlite3.connect(tmp_db)
    with conn:
        conn.execute(
            "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
            (str(tmp_path), "[]", "[]", 1),
        )
    writer = IndexWriter(conn)
    record = _synthetic_record(1, tmp_path)

    conn.execute("BEGIN")
    writer.bulk_upsert([record])
    conn.rollback()

    rows = conn.execute("SELECT path FROM files").fetchall()
    assert rows == []


def test_writer_bulk_upsert_temporarily_relaxes_synchronous_mode_for_top_level_transactions(
    tmp_db: Path, tmp_path: Path
) -> None:
    conn = sqlite3.connect(tmp_db)
    conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        (str(tmp_path), "[]", "[]", 1),
    )
    writer = IndexWriter(conn)
    before = conn.execute("PRAGMA synchronous").fetchone()

    assert writer.bulk_upsert([_synthetic_record(1, tmp_path)]) == 1

    after = conn.execute("PRAGMA synchronous").fetchone()
    assert before == (2,)
    assert after == (2,)


def test_writer_nested_transactions_keep_outer_synchronous_mode_unchanged(
    tmp_db: Path, tmp_path: Path
) -> None:
    conn = sqlite3.connect(tmp_db)
    conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        (str(tmp_path), "[]", "[]", 1),
    )
    conn.commit()
    writer = IndexWriter(conn)

    before = conn.execute("PRAGMA synchronous").fetchone()
    conn.execute("BEGIN")
    try:
        assert writer.bulk_upsert([_synthetic_record(1, tmp_path)]) == 1
        during = conn.execute("PRAGMA synchronous").fetchone()
    finally:
        conn.rollback()
    after = conn.execute("PRAGMA synchronous").fetchone()

    assert before == (2,)
    assert during == (2,)
    assert after == (2,)


def test_writer_apply_events_respects_active_transaction_rollback(tmp_db: Path, tmp_path: Path) -> None:
    conn = sqlite3.connect(tmp_db)
    with conn:
        conn.execute(
            "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
            (str(tmp_path), "[]", "[]", 1),
        )
    source = _synthetic_record(1, tmp_path)
    writer = IndexWriter(conn)
    assert writer.bulk_upsert([source]) == 1

    destination = tmp_path / "moved.txt"
    destination.write_text("moved", encoding="utf-8")

    conn.execute("BEGIN")
    writer.apply_events(
        [WatchEvent(event_type="moved", src_path=source.path, path=destination)],
        record_loader=make_record,
    )
    conn.rollback()

    rows = conn.execute("SELECT path FROM files ORDER BY path").fetchall()
    assert rows == [(str(source.path),)]
