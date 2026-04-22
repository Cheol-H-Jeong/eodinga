from __future__ import annotations

import sqlite3
from pathlib import Path

from eodinga.index.reader import find_by_path, list_roots, stats
from eodinga.index.writer import IndexWriter
from tests.conftest import make_record


def test_reader_helpers_report_counts_and_roots(tmp_db: Path, sample_tree) -> None:
    root = sample_tree()
    conn = sqlite3.connect(tmp_db)
    conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        (str(root), "[]", "[]", 1),
    )
    writer = IndexWriter(conn)
    records = [make_record(path) for path in sorted(root.rglob("*"))]
    writer.bulk_upsert(records)

    found = find_by_path(conn, root / "docs" / "guide.md")
    assert found is not None
    assert found.name == "guide.md"

    snapshot = stats(conn)
    assert snapshot.file_count == len(records)
    assert snapshot.dir_count == sum(1 for record in records if record.is_dir)
    assert snapshot.total_size >= 1
    assert list_roots(conn) == [Path(root)]
