from __future__ import annotations

import random
import statistics
from pathlib import Path
from time import perf_counter

from eodinga.index.writer import IndexWriter
from eodinga.query import search
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

FILE_COUNT = perf_int_env("EODINGA_PERF_FILTERED_QUERY_FILE_COUNT", 25_000)
QUERY_COUNT = perf_int_env("EODINGA_PERF_FILTERED_QUERY_COUNT", 750)
P95_LIMIT_MS = perf_float_env("EODINGA_PERF_FILTERED_QUERY_P95_MS", 45.0)


def test_filtered_content_query_latency(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    root.mkdir()
    conn = open_perf_db(tmp_path / "filtered-query-latency.db")
    try:
        insert_root(conn, root)

        def parser(path: Path):
            index = int(path.stem.split("-")[-1])
            token = "launch checklist" if index % 3 == 0 else "meeting notes"
            return make_parsed(path, token)

        writer = IndexWriter(conn, parser_callback=parser)
        records = []
        for index in range(FILE_COUNT):
            bucket = "archive" if index % 11 == 0 else f"group-{index % 64:02d}"
            path = root / bucket / f"report-{index:05d}.txt"
            records.append(make_file_record(path, size=index))
        writer.bulk_upsert(records)

        candidates = [index for index in range(FILE_COUNT) if index % 3 == 0 and index % 11 != 0]
        queries = [f'content:"launch checklist" -path:archive report-{random.choice(candidates):05d}' for _ in range(QUERY_COUNT)]

        latencies_ms: list[float] = []
        for query in queries:
            started = perf_counter()
            result = search(conn, query, limit=10)
            latencies_ms.append((perf_counter() - started) * 1000)
            assert result.hits

        p50 = statistics.quantiles(latencies_ms, n=100)[49]
        p95 = statistics.quantiles(latencies_ms, n=100)[94]
        p99 = statistics.quantiles(latencies_ms, n=100)[98]
        print(
            "filtered_query_latency "
            f"files={FILE_COUNT} count={QUERY_COUNT} "
            f"p50={p50:.2f}ms p95={p95:.2f}ms p99={p99:.2f}ms "
            f"limit_p95={P95_LIMIT_MS:.2f}ms"
        )
        assert p95 <= P95_LIMIT_MS
    finally:
        conn.close()
