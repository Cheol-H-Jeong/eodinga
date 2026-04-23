from __future__ import annotations

from pathlib import Path
from time import perf_counter

from eodinga.core.walker import walk_batched
from tests.perf._helpers import make_walk_rules, perf_float_env, perf_int_env, perf_only

pytestmark = perf_only

FILE_COUNT = perf_int_env("EODINGA_PERF_WALK_FILE_COUNT", 40_000)
MIN_RECORDS_PER_SECOND = perf_float_env("EODINGA_PERF_WALK_MIN_RPS", 25_000.0)


def _populate_tree(root: Path) -> int:
    root.mkdir()
    created = 0
    for index in range(FILE_COUNT):
        branch = root / f"group-{index % 256:03d}"
        branch.mkdir(exist_ok=True)
        (branch / f"file-{index:05d}.txt").touch()
        created += 1
    return created


def test_walk_batched_throughput(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    created = _populate_tree(root)

    started = perf_counter()
    indexed = sum(len(batch) for batch in walk_batched(root, make_walk_rules(root), root_id=1))
    elapsed = perf_counter() - started
    throughput = indexed / elapsed

    print(
        "walk_batched "
        f"records={indexed} elapsed={elapsed:.3f}s throughput={throughput:.0f} records/s "
        f"min_rps={MIN_RECORDS_PER_SECOND:.0f}"
    )
    assert indexed == created + 257
    assert throughput >= MIN_RECORDS_PER_SECOND
