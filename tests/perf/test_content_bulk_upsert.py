from __future__ import annotations

from pathlib import Path
from time import perf_counter

from eodinga.index.writer import IndexWriter
from tests.perf._helpers import (
    insert_root,
    make_file_record,
    make_parsed,
    open_perf_db,
    perf_float_env,
    perf_int_env,
    perf_only,
)

pytestmark = perf_only

FILE_COUNT = perf_int_env("EODINGA_PERF_CONTENT_BULK_FILE_COUNT", 10_000)
MIN_RECORDS_PER_SECOND = perf_float_env("EODINGA_PERF_CONTENT_BULK_MIN_RPS", 4_000.0)


def test_content_bulk_upsert_throughput(tmp_path: Path) -> None:
    root = tmp_path / "content-bulk"
    root.mkdir()
    conn = open_perf_db(tmp_path / "content-bulk-upsert.db")
    try:
        insert_root(conn, root)
        writer = IndexWriter(
            conn,
            parser_callback=lambda path: make_parsed(path, f"token-{hash(path.name) % 256:03d}"),
        )
        records = []
        for index in range(FILE_COUNT):
            branch = root / f"group-{index % 128:03d}"
            records.append(make_file_record(branch / f"doc-{index:05d}.txt", size=index))

        started = perf_counter()
        inserted = writer.bulk_upsert(records)
        elapsed = perf_counter() - started
        throughput = inserted / elapsed
        print(
            "content_bulk_upsert "
            f"records={inserted} elapsed={elapsed:.3f}s throughput={throughput:.0f} records/s "
            f"min_rps={MIN_RECORDS_PER_SECOND:.0f}"
        )
        assert inserted == FILE_COUNT
        assert throughput >= MIN_RECORDS_PER_SECOND
    finally:
        conn.close()
