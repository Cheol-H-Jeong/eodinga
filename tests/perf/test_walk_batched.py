from __future__ import annotations

from pathlib import Path
from time import perf_counter

from eodinga.core.walker import walk_batched
from tests.perf._helpers import make_walk_rules, perf_float_env, perf_int_env, perf_only

pytestmark = perf_only

DIR_COUNT = perf_int_env("EODINGA_PERF_WALK_DIR_COUNT", 64)
FILES_PER_DIR = perf_int_env("EODINGA_PERF_WALK_FILES_PER_DIR", 256)
MIN_RECORDS_PER_SECOND = perf_float_env("EODINGA_PERF_WALK_MIN_RPS", 25_000.0)


def test_walk_batched_throughput(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    root.mkdir()
    expected_records = 1
    for dir_index in range(DIR_COUNT):
        branch = root / f"group-{dir_index:03d}"
        branch.mkdir()
        expected_records += 1
        for file_index in range(FILES_PER_DIR):
            (branch / f"doc-{file_index:03d}.txt").write_text("payload", encoding="utf-8")
            expected_records += 1

    started = perf_counter()
    seen_records = sum(len(batch) for batch in walk_batched(root, make_walk_rules(root)))
    elapsed = perf_counter() - started
    throughput = seen_records / elapsed
    print(
        "walk_batched "
        f"records={seen_records} elapsed={elapsed:.3f}s throughput={throughput:.0f} records/s "
        f"min_rps={MIN_RECORDS_PER_SECOND:.0f}"
    )

    assert seen_records == expected_records
    assert throughput >= MIN_RECORDS_PER_SECOND
