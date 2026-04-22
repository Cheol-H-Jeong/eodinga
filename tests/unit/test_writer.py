from __future__ import annotations

import sqlite3
from pathlib import Path
from time import perf_counter, time

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
