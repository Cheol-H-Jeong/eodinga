# Performance

`eodinga` keeps the v0.1 perf checks opt-in. The suite is aligned with SPEC §6.3 and can be run locally with:

```bash
source .venv/bin/activate && EODINGA_RUN_PERF=1 pytest -q tests/perf -s
```

## Running the Suite

Use a warm local virtualenv and run the perf tests on an otherwise idle machine when you want comparable numbers.

```bash
source .venv/bin/activate
EODINGA_RUN_PERF=1 pytest -q tests/perf/test_cold_start.py -s
EODINGA_RUN_PERF=1 pytest -q tests/perf/test_bulk_upsert.py -s
EODINGA_RUN_PERF=1 pytest -q tests/perf/test_query_latency.py -s
EODINGA_RUN_PERF=1 pytest -q tests/perf/test_content_query.py -s
EODINGA_RUN_PERF=1 pytest -q tests/perf/test_watch_latency.py -s
```

The individual commands are useful when you are changing one subsystem and want a narrower regression signal before running the whole suite.

The current perf suite covers the SPEC §6.3 scenarios with smaller local-dev datasets:

- `tests/perf/test_cold_start.py`: walker + bulk index throughput on a real tmp tree.
- `tests/perf/test_bulk_upsert.py`: isolated writer throughput for 50k synthetic records.
- `tests/perf/test_query_latency.py`: name-only query latency against a 50k-file index.
- `tests/perf/test_content_query.py`: content query latency against a 5k-document corpus.
- `tests/perf/test_watch_latency.py`: file-create to query-visible latency through the watcher path.

## Baseline

Measured on 2026-04-23 in this repository’s Linux dev environment with `.venv` dependencies installed after the 0.1.47 bulk-write allocation trim:

| Benchmark | Dataset | Result |
| --- | --- | --- |
| Cold start | 20,201 indexed entries | 6,152 files/sec |
| Bulk upsert | 50k synthetic records | 61,103 records/sec |
| Name query latency | 2,000 queries / 50k files | p50 0.05 ms, p95 0.06 ms, p99 0.06 ms |
| Content query latency | 500 queries / 5k docs | p50 0.60 ms, p95 0.63 ms, p99 0.67 ms |
| Watch latency | 25 created files | p99 0.133 s |

These numbers are informational for v0.1, not release-blocking. The thresholds in `tests/perf/*` are set to catch clear regressions on a normal developer workstation rather than to enforce the SPEC’s reference-box targets. This round’s cold-start gain comes from trimming `IndexWriter.bulk_upsert()` overhead: list batches are now reused instead of copied, SQLite row tuples stream directly into `executemany()`, and unchanged content rows no longer trigger a `MAX(rowid)` probe on every pass.

## Interpreting Results

- `tests/perf/test_cold_start.py` exercises walker and bulk-upsert throughput. It is the best proxy for first-index regressions.
- `tests/perf/test_bulk_upsert.py` isolates the writer path when you want to distinguish SQLite insert churn from walker traversal cost.
- `tests/perf/test_query_latency.py` isolates name/path lookup cost without parser noise.
- `tests/perf/test_content_query.py` tracks content-index ranking and snippet latency.
- `tests/perf/test_watch_latency.py` measures file-create to query-visible lag through the watcher path.

The benchmarks intentionally stay below the full SPEC-scale datasets so they are practical in CI-like local runs, while still catching obvious algorithmic regressions.

## Reading the Numbers

- Re-run the same benchmark at least twice if the first sample is noisy; filesystem cache warmth heavily affects cold-start throughput.
- Treat query p95/p99 shifts as more meaningful than p50 for launcher responsiveness.
- Watch latency is end-to-end, so a regression there can come from debounce, event coalescing, or index commit timing rather than raw filesystem speed.
