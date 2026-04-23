from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from eodinga.common import WatchEvent
from eodinga.index.writer import IndexWriter
from tests.conftest import make_record
from tests.unit.test_writer import _synthetic_record


def test_writer_bulk_upsert_collapses_same_path_writes(
    tmp_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conn = sqlite3.connect(tmp_db)
    conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        (str(tmp_path), "[]", "[]", 1),
    )
    writer = IndexWriter(conn)
    record = _synthetic_record(1, tmp_path)
    seen_batch_sizes: list[int] = []
    original_upsert_records = writer._upsert_records

    def recording_upsert(records):  # type: ignore[no-untyped-def]
        seen_batch_sizes.append(len(records))
        return original_upsert_records(records)

    monkeypatch.setattr(writer, "_upsert_records", recording_upsert)

    assert writer.bulk_upsert([record, record, record]) == 3

    assert seen_batch_sizes == [1]


def test_writer_apply_events_collapses_same_path_writes(
    tmp_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conn = sqlite3.connect(tmp_db)
    conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        (str(tmp_path), "[]", "[]", 1),
    )
    writer = IndexWriter(conn)
    path = tmp_path / "live.txt"
    path.write_text("live", encoding="utf-8")
    seen_batch_sizes: list[int] = []
    original_upsert_records = writer._upsert_records

    def recording_upsert(records):  # type: ignore[no-untyped-def]
        seen_batch_sizes.append(len(records))
        return original_upsert_records(records)

    monkeypatch.setattr(writer, "_upsert_records", recording_upsert)

    processed = writer.apply_events(
        [
            WatchEvent(event_type="created", path=path),
            WatchEvent(event_type="modified", path=path),
        ],
        record_loader=make_record,
    )

    assert processed == 2
    assert seen_batch_sizes == [1]
