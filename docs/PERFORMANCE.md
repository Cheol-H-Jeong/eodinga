# Performance

`eodinga` keeps the v0.1 perf checks opt-in. The suite is aligned with SPEC §6.3 and can be run locally with:

```bash
source .venv/bin/activate && EODINGA_RUN_PERF=1 pytest -q tests/perf -s
```

The current perf suite covers the SPEC §6.3 scenarios with smaller local-dev datasets:

- `tests/perf/test_cold_start.py`: walker + bulk index throughput on a real tmp tree.
- `tests/perf/test_query_latency.py`: name-only query latency against a 50k-file index.
- `tests/perf/test_content_query.py`: content query latency against a 5k-document corpus.
- `tests/perf/test_watch_latency.py`: file-create to query-visible latency through the watcher path.

## Baseline

Measured on 2026-04-23 in this repository’s Linux dev environment with `.venv` dependencies installed:

| Benchmark | Dataset | Result |
| --- | --- | --- |
| Cold start | 20,201 indexed entries | 4,333 files/sec |
| Name query latency | 2,000 queries / 50k files | p50 0.05 ms, p95 0.06 ms, p99 0.08 ms |
| Content query latency | 500 queries / 5k docs | p50 0.60 ms, p95 0.63 ms, p99 0.66 ms |
| Watch latency | 25 created files | p99 0.132 s |

These numbers are informational for v0.1, not release-blocking. The thresholds in `tests/perf/*` are set to catch clear regressions on a normal developer workstation rather than to enforce the SPEC’s reference-box targets. The cold-start benchmark now uses an explicit include rule for its temporary fixture root so it exercises the real walker path without being filtered by the default `/tmp` safety denylist, and its guardrail is intentionally set below the measured baseline so machine variance and background load do not create false failures.

## Interpreting Results

- `tests/perf/test_cold_start.py` exercises walker and bulk-upsert throughput. It is the best proxy for first-index regressions.
- `tests/perf/test_query_latency.py` isolates name/path lookup cost without parser noise.
- `tests/perf/test_content_query.py` tracks content-index ranking and snippet latency.
- `tests/perf/test_watch_latency.py` measures file-create to query-visible lag through the watcher path.

The benchmarks intentionally stay below the full SPEC-scale datasets so they are practical in CI-like local runs, while still catching obvious algorithmic regressions.
