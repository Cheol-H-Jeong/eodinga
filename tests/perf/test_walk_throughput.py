from __future__ import annotations

from pathlib import Path
from time import perf_counter

from eodinga.core.walker import walk_batched
from tests.perf._helpers import make_walk_rules, perf_float_env, perf_int_env, perf_only

pytestmark = perf_only

FILE_COUNT = perf_int_env("EODINGA_PERF_WALK_FILE_COUNT", 50_000)
MIN_FILES_PER_SECOND = perf_float_env("EODINGA_PERF_WALK_MIN_FPS", 5_000.0)


def _populate_tree(root: Path) -> int:
    root.mkdir()
    for index in range(FILE_COUNT):
        branch = root / f"group-{index % 200:03d}"
        branch.mkdir(exist_ok=True)
        (branch / f"file-{index:05d}.txt").write_text("x", encoding="utf-8")
    return FILE_COUNT


def test_walk_batched_throughput(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    created = _populate_tree(root)

    started = perf_counter()
    walked = sum(len(batch) for batch in walk_batched(root, make_walk_rules(root), root_id=1))
    elapsed = perf_counter() - started
    throughput = walked / elapsed

    print(
        "walk_throughput "
        f"files={walked} elapsed={elapsed:.3f}s throughput={throughput:.0f} files/s "
        f"min_fps={MIN_FILES_PER_SECOND:.0f}"
    )
    assert walked == created + 201
    assert throughput >= MIN_FILES_PER_SECOND
