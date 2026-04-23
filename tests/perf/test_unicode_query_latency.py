from __future__ import annotations

import statistics
import unicodedata
from pathlib import Path
from time import perf_counter

from eodinga.index.writer import IndexWriter
from eodinga.query import search
from tests.perf._helpers import (
    insert_root,
    make_file_record,
    open_perf_db,
    perf_float_env,
    perf_int_env,
    perf_only,
)

pytestmark = perf_only

FILE_COUNT = perf_int_env("EODINGA_PERF_UNICODE_QUERY_FILE_COUNT", 20_000)
QUERY_COUNT = perf_int_env("EODINGA_PERF_UNICODE_QUERY_COUNT", 200)
P95_LIMIT_MS = perf_float_env("EODINGA_PERF_UNICODE_QUERY_P95_MS", 90.0)


def test_unicode_filename_query_latency(tmp_path: Path) -> None:
    root = tmp_path / "unicode-tree"
    root.mkdir()
    query = "회의록"
    decomposed_query = unicodedata.normalize("NFD", query)
    conn = open_perf_db(tmp_path / "unicode-query.db")
    try:
        insert_root(conn, root)
        writer = IndexWriter(conn)
        records = []
        for index in range(FILE_COUNT):
            branch = root / f"group-{index % 128:03d}"
            if index % 5 == 0:
                name = f"{decomposed_query}-report-{index:05d}.txt"
            else:
                name = f"archive-{index:05d}.txt"
            records.append(make_file_record(branch / name, size=index))
        writer.bulk_upsert(records)

        latencies_ms: list[float] = []
        for _ in range(QUERY_COUNT):
            started = perf_counter()
            result = search(conn, query, limit=10)
            latencies_ms.append((perf_counter() - started) * 1000)
            assert result.hits

        p50 = statistics.quantiles(latencies_ms, n=100)[49]
        p95 = statistics.quantiles(latencies_ms, n=100)[94]
        p99 = statistics.quantiles(latencies_ms, n=100)[98]
        print(
            "unicode_query_latency "
            f"files={FILE_COUNT} count={QUERY_COUNT} "
            f"p50={p50:.2f}ms p95={p95:.2f}ms p99={p99:.2f}ms "
            f"limit_p95={P95_LIMIT_MS:.2f}ms"
        )
        assert p95 <= P95_LIMIT_MS
    finally:
        conn.close()
