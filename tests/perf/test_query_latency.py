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

FILE_COUNT = perf_int_env("EODINGA_PERF_QUERY_FILE_COUNT", 50_000)
QUERY_COUNT = perf_int_env("EODINGA_PERF_QUERY_COUNT", 2_000)
P95_LIMIT_MS = perf_float_env("EODINGA_PERF_QUERY_P95_MS", 30.0)
ROOT_SCOPE_FILE_COUNT = perf_int_env("EODINGA_PERF_QUERY_ROOT_FILE_COUNT", 25_000)
ROOT_SCOPE_QUERY_COUNT = perf_int_env("EODINGA_PERF_QUERY_ROOT_COUNT", 1_000)
ROOT_SCOPE_P95_LIMIT_MS = perf_float_env("EODINGA_PERF_QUERY_ROOT_P95_MS", 35.0)


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
        print(
            "query_latency "
            f"files={FILE_COUNT} count={QUERY_COUNT} "
            f"p50={p50:.2f}ms p95={p95:.2f}ms p99={p99:.2f}ms "
            f"limit_p95={P95_LIMIT_MS:.2f}ms"
        )
        assert p95 <= P95_LIMIT_MS
    finally:
        conn.close()


def test_root_scoped_query_latency(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    reports = root / "reports"
    archive = root / "archive"
    reports.mkdir(parents=True)
    archive.mkdir(parents=True)
    conn = open_perf_db(tmp_path / "query-root-latency.db")
    try:
        insert_root(conn, root)
        writer = IndexWriter(conn)
        records = []
        for index in range(ROOT_SCOPE_FILE_COUNT):
            branch = reports if index % 2 == 0 else archive
            name = (
                f"release-{index:05d}.md"
                if index % 5 == 0
                else f"notes-{index:05d}.txt"
            )
            records.append(make_file_record(branch / name, size=index))
        writer.bulk_upsert(records)

        queries = [f"release-{random.randrange(ROOT_SCOPE_FILE_COUNT // 10) * 10:05d}" for _ in range(ROOT_SCOPE_QUERY_COUNT)]
        latencies_ms: list[float] = []
        for query in queries:
            started = perf_counter()
            result = search(conn, query, limit=10, root=Path(str(reports).replace("/", "\\")))
            latencies_ms.append((perf_counter() - started) * 1000)
            assert result.hits
            assert all(str(hit.file.path).startswith(str(reports)) for hit in result.hits)

        p50 = statistics.quantiles(latencies_ms, n=100)[49]
        p95 = statistics.quantiles(latencies_ms, n=100)[94]
        p99 = statistics.quantiles(latencies_ms, n=100)[98]
        print(
            "root_scoped_query_latency "
            f"files={ROOT_SCOPE_FILE_COUNT} count={ROOT_SCOPE_QUERY_COUNT} "
            f"p50={p50:.2f}ms p95={p95:.2f}ms p99={p99:.2f}ms "
            f"limit_p95={ROOT_SCOPE_P95_LIMIT_MS:.2f}ms"
        )
        assert p95 <= ROOT_SCOPE_P95_LIMIT_MS
    finally:
        conn.close()
