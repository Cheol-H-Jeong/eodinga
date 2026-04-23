from __future__ import annotations

import random
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
QUERY_COUNT = perf_int_env("EODINGA_PERF_UNICODE_QUERY_COUNT", 250)
P95_LIMIT_MS = perf_float_env("EODINGA_PERF_UNICODE_QUERY_P95_MS", 80.0)


def test_unicode_name_query_latency(tmp_path: Path) -> None:
    root = tmp_path / "unicode-tree"
    root.mkdir()
    conn = open_perf_db(tmp_path / "unicode-query-latency.db")
    try:
        insert_root(conn, root)
        writer = IndexWriter(conn)
        records = []
        for index in range(FILE_COUNT):
            folder = root / f"group-{index % 128:03d}"
            base_name = f"회의록-{index:05d}.txt" if index % 4 == 0 else f"노트-{index:05d}.txt"
            name = (
                unicodedata.normalize("NFD", base_name)
                if index % 3 == 0
                else unicodedata.normalize("NFC", base_name)
            )
            records.append(make_file_record(folder / name, size=index))
        writer.bulk_upsert(records)

        queries = [
            unicodedata.normalize("NFD" if index % 2 else "NFC", "회의록")
            for index in range(QUERY_COUNT)
        ]
        random.shuffle(queries)
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
            "unicode_query_latency "
            f"files={FILE_COUNT} count={QUERY_COUNT} "
            f"p50={p50:.2f}ms p95={p95:.2f}ms p99={p99:.2f}ms "
            f"limit_p95={P95_LIMIT_MS:.2f}ms"
        )
        assert p95 <= P95_LIMIT_MS
    finally:
        conn.close()
