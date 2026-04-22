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
    perf_only,
)

pytestmark = perf_only

DOC_COUNT = 5_000
QUERY_COUNT = 500
P95_LIMIT_MS = 150.0


def test_content_query_latency(tmp_path: Path) -> None:
    root = tmp_path / "docs"
    root.mkdir()
    tokens = [f"topic-{index:03d}" for index in range(100)]
    conn = open_perf_db(tmp_path / "content-query.db")
    try:
        insert_root(conn, root)
        records = []
        parsed_map = {}
        for index in range(DOC_COUNT):
            path = root / f"doc-{index:05d}.md"
            token = tokens[index % len(tokens)]
            records.append(make_file_record(path, size=2048 + index))
            parsed_map[path] = make_parsed(path, token)
        writer = IndexWriter(conn, parser_callback=lambda path: parsed_map.get(path))
        writer.bulk_upsert(records)

        queries = [f"content:{random.choice(tokens)}" for _ in range(QUERY_COUNT)]
        latencies_ms: list[float] = []
        for query in queries:
            started = perf_counter()
            result = search(conn, query, limit=10)
            latencies_ms.append((perf_counter() - started) * 1000)
            assert result.hits

        p50 = statistics.quantiles(latencies_ms, n=100)[49]
        p95 = statistics.quantiles(latencies_ms, n=100)[94]
        p99 = statistics.quantiles(latencies_ms, n=100)[98]
        print(f"content_query count={QUERY_COUNT} p50={p50:.2f}ms p95={p95:.2f}ms p99={p99:.2f}ms")
        assert p95 <= P95_LIMIT_MS
    finally:
        conn.close()

