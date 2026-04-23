from __future__ import annotations

import random
import statistics
from pathlib import Path
from time import perf_counter

from eodinga.query import search
from eodinga.index.writer import IndexWriter
from tests.perf._helpers import (
    insert_root,
    make_file_record,
    open_perf_db,
    perf_float_env,
    perf_int_env,
    perf_only,
)

pytestmark = perf_only

FILES_PER_ROOT = perf_int_env("EODINGA_PERF_SCOPED_QUERY_FILE_COUNT", 20_000)
QUERY_COUNT = perf_int_env("EODINGA_PERF_SCOPED_QUERY_COUNT", 1_000)
P95_LIMIT_MS = perf_float_env("EODINGA_PERF_SCOPED_QUERY_P95_MS", 30.0)


def test_root_scoped_name_query_latency(tmp_path: Path) -> None:
    roots = [tmp_path / "alpha", tmp_path / "beta"]
    conn = open_perf_db(tmp_path / "scoped-query.db")
    try:
        writer = IndexWriter(conn)
        records = []
        for root_id, root in enumerate(roots, start=1):
            root.mkdir()
            insert_root(conn, root)
            prefix = root.name
            for index in range(FILES_PER_ROOT):
                group = root / f"group-{index % 128:03d}"
                name = f"{prefix}-report-{index:05d}.txt"
                records.append(make_file_record(group / name, root_id=root_id, size=index))
        writer.bulk_upsert(records)

        # Warm the query and statement caches before measuring steady-state latency.
        assert search(conn, "alpha-report-00000", limit=10, root=roots[0]).hits

        queries = [
            f"alpha-report-{random.randrange(FILES_PER_ROOT):05d}" for _ in range(QUERY_COUNT)
        ]
        latencies_ms: list[float] = []
        for query in queries:
            started = perf_counter()
            result = search(conn, query, limit=10, root=roots[0])
            latencies_ms.append((perf_counter() - started) * 1000)
            assert result.hits
            assert all(str(hit.file.path).startswith(str(roots[0])) for hit in result.hits)

        p50 = statistics.quantiles(latencies_ms, n=100)[49]
        p95 = statistics.quantiles(latencies_ms, n=100)[94]
        p99 = statistics.quantiles(latencies_ms, n=100)[98]
        print(
            "scoped_query_latency "
            f"files_per_root={FILES_PER_ROOT} count={QUERY_COUNT} "
            f"p50={p50:.2f}ms p95={p95:.2f}ms p99={p99:.2f}ms "
            f"limit_p95={P95_LIMIT_MS:.2f}ms"
        )
        assert p95 <= P95_LIMIT_MS
    finally:
        conn.close()
