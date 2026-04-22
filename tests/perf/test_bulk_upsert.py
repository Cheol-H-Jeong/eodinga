from __future__ import annotations

from pathlib import Path
from time import perf_counter

from eodinga.index.writer import IndexWriter
from tests.perf._helpers import insert_root, make_file_record, open_perf_db, perf_only

pytestmark = perf_only

FILE_COUNT = 50_000
MIN_RECORDS_PER_SECOND = 20_000.0


def test_bulk_upsert_throughput(tmp_path: Path) -> None:
    root = tmp_path / "bulk"
    root.mkdir()
    conn = open_perf_db(tmp_path / "bulk-upsert.db")
    try:
        insert_root(conn, root)
        writer = IndexWriter(conn)
        records = []
        for index in range(FILE_COUNT):
            branch = root / f"group-{index % 256:03d}"
            records.append(make_file_record(branch / f"file-{index:05d}.txt", size=index))

        started = perf_counter()
        inserted = writer.bulk_upsert(records)
        elapsed = perf_counter() - started
        throughput = inserted / elapsed
        print(
            f"bulk_upsert records={inserted} elapsed={elapsed:.3f}s throughput={throughput:.0f} records/s"
        )
        assert inserted == FILE_COUNT
        assert throughput >= MIN_RECORDS_PER_SECOND
    finally:
        conn.close()
