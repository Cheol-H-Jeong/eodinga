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
    make_parsed,
    open_perf_db,
    perf_float_env,
    perf_int_env,
    perf_only,
)

pytestmark = perf_only

DOC_COUNT = perf_int_env("EODINGA_PERF_QUERY_FALLBACK_DOC_COUNT", 20_000)
QUERY_COUNT = perf_int_env("EODINGA_PERF_QUERY_FALLBACK_COUNT", 250)
P95_LIMIT_MS = perf_float_env("EODINGA_PERF_QUERY_FALLBACK_P95_MS", 60.0)


def test_phrase_and_unicode_query_latency(tmp_path: Path) -> None:
    root = tmp_path / "docs"
    root.mkdir()
    conn = open_perf_db(tmp_path / "query-fallback-latency.db")
    try:
        insert_root(conn, root)
        tokens = [f"회의록-{index:03d}" for index in range(64)]
        parsed_map = {}
        records = []
        for index in range(DOC_COUNT):
            branch = root / f"group-{index % 128:03d}"
            path = branch / f"project-notes-{index:05d}.md"
            token = tokens[index % len(tokens)]
            records.append(make_file_record(path, size=4096 + index))
            parsed_map[path] = make_parsed(path, token)
        writer = IndexWriter(conn, parser_callback=lambda path: parsed_map.get(path))
        writer.bulk_upsert(records)

        queries = [random.choice(tokens) for _ in range(QUERY_COUNT)]
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
            "query_fallback_latency "
            f"docs={DOC_COUNT} count={QUERY_COUNT} "
            f"p50={p50:.2f}ms p95={p95:.2f}ms p99={p99:.2f}ms "
            f"limit_p95={P95_LIMIT_MS:.2f}ms"
        )
        assert p95 <= P95_LIMIT_MS
    finally:
        conn.close()
