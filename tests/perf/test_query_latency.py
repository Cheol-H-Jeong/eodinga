from __future__ import annotations

import random
import statistics
from pathlib import Path
from time import perf_counter

from eodinga.query import search
from eodinga.index.writer import IndexWriter
from tests.perf._helpers import insert_root, make_file_record, open_perf_db, perf_only

pytestmark = perf_only

FILE_COUNT = 50_000
QUERY_COUNT = 2_000
P95_LIMIT_MS = 30.0


def test_name_query_latency(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    root.mkdir()
    conn = open_perf_db(tmp_path / "query-latency.db")
    try:
        insert_root(conn, root)
        writer = IndexWriter(conn)
        records = []
        for index in range(FILE_COUNT):
            group = root / f"group-{index % 128:03d}"
            name = f"report-{index:05d}.txt" if index % 5 == 0 else f"note-{index:05d}.txt"
            records.append(make_file_record(group / name, size=index))
        writer.bulk_upsert(records)

        queries = [f"report-{random.randrange(FILE_COUNT // 5) * 5:05d}" for _ in range(QUERY_COUNT)]
        latencies_ms: list[float] = []
        for query in queries:
            started = perf_counter()
            result = search(conn, query, limit=10)
            latencies_ms.append((perf_counter() - started) * 1000)
            assert result.hits

        p50 = statistics.quantiles(latencies_ms, n=100)[49]
        p95 = statistics.quantiles(latencies_ms, n=100)[94]
        p99 = statistics.quantiles(latencies_ms, n=100)[98]
        print(f"query_latency count={QUERY_COUNT} p50={p50:.2f}ms p95={p95:.2f}ms p99={p99:.2f}ms")
        assert p95 <= P95_LIMIT_MS
    finally:
        conn.close()
