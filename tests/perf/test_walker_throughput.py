from __future__ import annotations

from pathlib import Path
from time import perf_counter

from eodinga.core.walker import walk_batched
from tests.perf._helpers import make_walk_rules, perf_float_env, perf_int_env, perf_only

pytestmark = perf_only

FILE_COUNT = perf_int_env("EODINGA_PERF_WALK_FILE_COUNT", 25_000)
MIN_ENTRIES_PER_SECOND = perf_float_env("EODINGA_PERF_WALK_MIN_EPS", 5_000.0)


def _populate_tree(root: Path) -> tuple[int, int]:
    file_count = 0
    dir_names: set[Path] = set()
    root.mkdir()
    for index in range(FILE_COUNT):
        branch = root / f"dir-{index % 250:03d}"
        branch.mkdir(exist_ok=True)
        dir_names.add(branch)
        (branch / f"file-{index:05d}.txt").touch()
        file_count += 1
    return file_count, len(dir_names) + 1


def test_walk_batched_throughput(tmp_path: Path) -> None:
    root = tmp_path / "walk-tree"
    created_files, created_dirs = _populate_tree(root)

    started = perf_counter()
    records = [record for batch in walk_batched(root, make_walk_rules(root), root_id=1) for record in batch]
    elapsed = perf_counter() - started
    throughput = len(records) / elapsed
    print(
        "walker_throughput "
        f"entries={len(records)} elapsed={elapsed:.3f}s throughput={throughput:.0f} entries/s "
        f"min_eps={MIN_ENTRIES_PER_SECOND:.0f}"
    )

    assert len(records) == created_files + created_dirs
    assert throughput >= MIN_ENTRIES_PER_SECOND
