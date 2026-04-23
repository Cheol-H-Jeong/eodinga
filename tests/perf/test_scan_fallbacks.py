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

UNICODE_FILE_COUNT = perf_int_env("EODINGA_PERF_UNICODE_FILE_COUNT", 20_000)
UNICODE_QUERY_COUNT = perf_int_env("EODINGA_PERF_UNICODE_QUERY_COUNT", 400)
UNICODE_P95_LIMIT_MS = perf_float_env("EODINGA_PERF_UNICODE_P95_MS", 45.0)
PARSED_BULK_FILE_COUNT = perf_int_env("EODINGA_PERF_PARSED_BULK_FILE_COUNT", 8_000)
PARSED_BULK_MIN_RPS = perf_float_env("EODINGA_PERF_PARSED_BULK_MIN_RPS", 3_000.0)


def test_unicode_path_scan_latency(tmp_path: Path) -> None:
    root = tmp_path / "unicode-tree"
    root.mkdir()
    conn = open_perf_db(tmp_path / "unicode-scan.db")
    try:
        insert_root(conn, root)
        writer = IndexWriter(conn)
        records = []
        for index in range(UNICODE_FILE_COUNT):
            team = f"팀-{index % 64:02d}"
            suffix = "회의록" if index % 4 == 0 else "보고서"
            records.append(make_file_record(root / team / f"프로젝트-{index:05d}-{suffix}.txt", size=index))
        writer.bulk_upsert(records)

        queries = [f"프로젝트-{random.randrange(UNICODE_FILE_COUNT):05d}" for _ in range(UNICODE_QUERY_COUNT)]
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
            "unicode_path_scan "
            f"files={UNICODE_FILE_COUNT} count={UNICODE_QUERY_COUNT} "
            f"p50={p50:.2f}ms p95={p95:.2f}ms p99={p99:.2f}ms "
            f"limit_p95={UNICODE_P95_LIMIT_MS:.2f}ms"
        )
        assert p95 <= UNICODE_P95_LIMIT_MS
    finally:
        conn.close()


def test_parsed_bulk_upsert_throughput(tmp_path: Path) -> None:
    root = tmp_path / "parsed-bulk"
    root.mkdir()
    conn = open_perf_db(tmp_path / "parsed-bulk.db")
    try:
        insert_root(conn, root)
        records = []
        parsed_map = {}
        for index in range(PARSED_BULK_FILE_COUNT):
            path = root / f"doc-{index:05d}.md"
            token = f"topic-{index % 128:03d}"
            records.append(make_file_record(path, size=1024 + index))
            parsed_map[path] = make_parsed(path, token)
        writer = IndexWriter(conn, parser_callback=lambda path: parsed_map.get(path))

        started = perf_counter()
        inserted = writer.bulk_upsert(records)
        elapsed = perf_counter() - started
        throughput = inserted / elapsed
        print(
            "parsed_bulk_upsert "
            f"records={inserted} elapsed={elapsed:.3f}s throughput={throughput:.0f} records/s "
            f"min_rps={PARSED_BULK_MIN_RPS:.0f}"
        )
        assert inserted == PARSED_BULK_FILE_COUNT
        assert throughput >= PARSED_BULK_MIN_RPS
    finally:
        conn.close()
