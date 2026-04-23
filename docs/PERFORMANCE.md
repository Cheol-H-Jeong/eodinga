# Performance

`eodinga` keeps the v0.1 perf checks opt-in. The suite is aligned with SPEC §6.3 and can be run locally with:

```bash
source .venv/bin/activate && EODINGA_RUN_PERF=1 pytest -q tests/perf -s
```

The shipped datasets stay small enough for local developer runs, but each benchmark now accepts env overrides so you can scale toward the SPEC reference-box shapes without editing test code.

## Running the Suite

Use a warm local virtualenv and run the perf tests on an otherwise idle machine when you want comparable numbers.

```bash
source .venv/bin/activate
EODINGA_RUN_PERF=1 pytest -q tests/perf/test_cold_start.py -s
EODINGA_RUN_PERF=1 pytest -q tests/perf/test_bulk_upsert.py -s
EODINGA_RUN_PERF=1 pytest -q tests/perf/test_content_bulk_upsert.py -s
EODINGA_RUN_PERF=1 pytest -q tests/perf/test_query_latency.py -s
EODINGA_RUN_PERF=1 pytest -q tests/perf/test_content_query.py -s
EODINGA_RUN_PERF=1 pytest -q tests/perf/test_watch_latency.py -s
```

The individual commands are useful when you are changing one subsystem and want a narrower regression signal before running the whole suite.

The current perf suite covers the SPEC §6.3 scenarios with smaller local-dev datasets:

- `tests/perf/test_cold_start.py`: walker + bulk index throughput on a real tmp tree.
- `tests/perf/test_cold_start.py::test_rebuild_cold_start_throughput`: staged rebuild throughput through the real `rebuild_index()` entry point.
- `tests/perf/test_bulk_upsert.py`: isolated writer throughput for 50k synthetic records.
- `tests/perf/test_content_bulk_upsert.py`: content-aware writer throughput with synthetic parser output.
- `tests/perf/test_query_latency.py`: name-only query latency against a 50k-file index.
- `tests/perf/test_content_query.py`: content query latency against a 5k-document corpus.
- `tests/perf/test_watch_latency.py`: file-create to query-visible latency through the watcher path.

Each benchmark prints a structured summary line to stdout. Capture those lines directly in commit notes or a scratch file when you refresh the baseline so the numbers in this document remain auditable against the exact test output.

## Scaling Knobs

Use env vars to raise workload size or tighten/relax the informational gate for a single run:

```bash
source .venv/bin/activate
EODINGA_RUN_PERF=1 \
EODINGA_PERF_COLD_START_FILE_COUNT=100000 \
EODINGA_PERF_QUERY_FILE_COUNT=250000 \
EODINGA_PERF_QUERY_COUNT=10000 \
EODINGA_PERF_CONTENT_DOC_COUNT=20000 \
pytest -q tests/perf -s
```

Supported overrides:

- `EODINGA_PERF_COLD_START_FILE_COUNT`, `EODINGA_PERF_COLD_START_MIN_FPS`
- `EODINGA_PERF_REBUILD_MIN_FPS`
- `EODINGA_PERF_BULK_FILE_COUNT`, `EODINGA_PERF_BULK_MIN_RPS`
- `EODINGA_PERF_CONTENT_BULK_FILE_COUNT`, `EODINGA_PERF_CONTENT_BULK_MIN_RPS`
- `EODINGA_PERF_QUERY_FILE_COUNT`, `EODINGA_PERF_QUERY_COUNT`, `EODINGA_PERF_QUERY_P95_MS`
- `EODINGA_PERF_CONTENT_DOC_COUNT`, `EODINGA_PERF_CONTENT_QUERY_COUNT`, `EODINGA_PERF_CONTENT_P95_MS`
- `EODINGA_PERF_WATCH_FILE_COUNT`, `EODINGA_PERF_WATCH_P99_SECONDS`

The defaults currently checked into the suite are:

| Benchmark | Size knobs | Gate knobs |
| --- | --- | --- |
| Cold start | `EODINGA_PERF_COLD_START_FILE_COUNT=20000` | `EODINGA_PERF_COLD_START_MIN_FPS=4000`, `EODINGA_PERF_REBUILD_MIN_FPS=3500` |
| Bulk upsert | `EODINGA_PERF_BULK_FILE_COUNT=50000` | `EODINGA_PERF_BULK_MIN_RPS=20000` |
| Content bulk upsert | `EODINGA_PERF_CONTENT_BULK_FILE_COUNT=10000` | `EODINGA_PERF_CONTENT_BULK_MIN_RPS=4000` |
| Name query | `EODINGA_PERF_QUERY_FILE_COUNT=50000`, `EODINGA_PERF_QUERY_COUNT=2000` | `EODINGA_PERF_QUERY_P95_MS=30` |
| Content query | `EODINGA_PERF_CONTENT_DOC_COUNT=5000`, `EODINGA_PERF_CONTENT_QUERY_COUNT=500` | `EODINGA_PERF_CONTENT_P95_MS=150` |
| Watch latency | `EODINGA_PERF_WATCH_FILE_COUNT=25` | `EODINGA_PERF_WATCH_P99_SECONDS=2.0` |

## Baseline

Measured on 2026-04-23 in this repository’s Linux dev environment with `.venv` dependencies installed on the branch that originally introduced the current no-parser indexing fast path:

| Benchmark | Dataset | Result |
| --- | --- | --- |
| Cold start | 20,201 indexed entries | 6,059 files/sec |
| Rebuild cold start | 20,201 indexed entries via `rebuild_index()` | 6,537 files/sec |
| Bulk upsert | 50k synthetic records | 56,222 records/sec |
| Name query latency | 2,000 queries / 50k files | p50 0.06 ms, p95 0.06 ms, p99 0.07 ms |
| Content query latency | 500 queries / 5k docs | p50 0.60 ms, p95 0.63 ms, p99 0.67 ms |
| Watch latency | 25 created files | p99 0.133 s |

These numbers are informational for v0.1, not release-blocking. The thresholds in `tests/perf/*` are set to catch clear regressions on a normal developer workstation rather than to enforce the SPEC’s reference-box targets. The benchmark set reflects the checked-in no-parser fast path, where metadata-only indexing avoids the guaranteed-empty content upsert pass when no parser callback is installed.

When you refresh this table, record:

1. The command you ran.
2. The printed benchmark summary line.
3. Any non-default env overrides that changed dataset size or gate thresholds.
4. Whether the run was warm-cache or after a cold filesystem cache reset.

## Baseline Freshness Policy

- Treat the table above as a recorded benchmark sample, not an implicit claim about the current `HEAD`.
- If you did not rerun the perf suite in the same round, leave the numeric table untouched and document your change elsewhere.
- If you do rerun the suite, update the measurement date, note the exact command, and describe the code or docs change that explains the new sample.
- When a README or release guide cites the perf baseline, describe it as the "current checked-in baseline" unless the benchmark was rerun at the same commit being released.

## Benchmark Evidence Bundle

When you refresh the checked-in baseline, keep these items together:

- the exact `pytest -q tests/perf ... -s` command
- the raw stdout summary lines
- every non-default `EODINGA_PERF_*` override
- whether the run used a warm cache or a deliberately cold filesystem cache
- the commit that the sample is meant to describe

If you cannot provide all five, leave the baseline table alone and document the run as an out-of-band measurement instead.

## If The Perf Run Fails

- Do not overwrite the baseline table with numbers from a failing run.
- Capture the printed summary lines and the first failing threshold in the same note or handoff so the regression stays reviewable.
- Treat the failure as diagnostic evidence for the subsystem you changed, not as a reason to quietly relax the documented baseline.
- Keep the default release gate and the opt-in perf run separate in status reports; `pytest -q tests` staying green does not mean the perf suite was exercised.
- If debug logging pollutes stdout, keep the raw log and extract only the benchmark summary prefixes before updating any documentation.

One-command capture example:

```bash
source .venv/bin/activate && EODINGA_RUN_PERF=1 pytest -q tests/perf -s 2>&1 | tee /tmp/eodinga-perf.log && rg '^(bulk_upsert|cold_start|rebuild_cold_start|rebuild_index|walk_batched|query_latency|content_query_latency|watch_latency)' /tmp/eodinga-perf.log
```

## Repro Checklist

Use this short checklist before replacing the baseline table:

1. Reuse the same virtualenv and dependency set used for the current branch.
2. Note whether the machine was otherwise idle and whether the filesystem cache was warm.
3. Capture the exact stdout summary line from the perf test instead of paraphrasing the result.
4. Record every non-default `EODINGA_PERF_*` override next to the benchmark output.
5. Update the document only after a repeat run lands in the same range.

## Interpreting Results

- `tests/perf/test_cold_start.py` exercises walker and bulk-upsert throughput. It is the best low-level proxy for first-index regressions.
- `tests/perf/test_cold_start.py::test_rebuild_cold_start_throughput` measures the actual staged rebuild path, including temp-index creation and atomic swap.
- `tests/perf/test_bulk_upsert.py` isolates the writer path when you want to distinguish SQLite insert churn from walker traversal cost.
- `tests/perf/test_content_bulk_upsert.py` isolates the parser-enabled writer path so metadata-only gains do not hide content-index regressions.
- `tests/perf/test_query_latency.py` isolates name/path lookup cost without parser noise.
- `tests/perf/test_content_query.py` tracks content-index ranking and snippet latency.
- `tests/perf/test_watch_latency.py` measures file-create to query-visible lag through the watcher path.

The benchmarks intentionally stay below the full SPEC-scale datasets so they are practical in CI-like local runs, while still catching obvious algorithmic regressions.

## Reading the Numbers

- Re-run the same benchmark at least twice if the first sample is noisy; filesystem cache warmth heavily affects cold-start throughput.
- Treat query p95/p99 shifts as more meaningful than p50 for launcher responsiveness.
- Watch latency is end-to-end, so a regression there can come from debounce, event coalescing, or index commit timing rather than raw filesystem speed.

## Profiling Workflow

1. Start with the narrowest perf target that matches the subsystem you changed.
2. Re-run the same test once to separate one-off cache noise from a real regression.
3. If the regression is in cold start, compare `test_cold_start.py` with `test_bulk_upsert.py` to decide whether the walker or writer moved.
4. If the regression is in watch visibility, inspect coalescing, debounce, and commit timing before touching query ranking.
5. Refresh this document only after you have rerun the benchmark in the same local environment and the result is stable enough to be explanatory.

## Practical Threshold Notes

- The shipped thresholds are intentionally lower than the SPEC reference-box targets so developer laptops and CI-like hosts can still catch algorithmic regressions.
- Query latency benchmarks are most useful as relative comparisons across rounds; the absolute number depends heavily on cache warmth and SQLite page cache state.
- Content-query numbers move with parser output volume as much as with ranking logic, so compare corpus shape before attributing a slowdown to the executor.
- Watch-latency failures should be read as an end-to-end signal; check watchdog delivery, event batching, SQLite commit timing, and query visibility before assuming the bottleneck is filesystem notification latency itself.

## Release Use

- Perf results are informational for `0.1.x`; they do not replace the default acceptance gate.
- A perf-table refresh belongs in the same round only when the benchmark was rerun at the current HEAD and the documented numbers come from that run.
- If a code or docs round did not rerun the benchmark, leave the baseline table alone and avoid pretending the old numbers describe the new tip exactly.
- If a same-round perf run failed, report the failing summary lines separately and leave the checked-in baseline untouched until the regression is understood.
