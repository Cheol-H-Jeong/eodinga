from __future__ import annotations

from pathlib import Path
from time import perf_counter

from eodinga.core.walker import walk_batched
from tests.perf._helpers import make_walk_rules, perf_float_env, perf_int_env, perf_only

pytestmark = perf_only

FILE_COUNT = perf_int_env("EODINGA_PERF_WALK_FILE_COUNT", 40_000)
MIN_FILES_PER_SECOND = perf_float_env("EODINGA_PERF_WALK_MIN_FPS", 8_000.0)


def test_walk_batched_throughput(tmp_path: Path) -> None:
    root = tmp_path / "walk"
    root.mkdir()
    for index in range(FILE_COUNT):
        branch = root / f"group-{index % 256:03d}"
        branch.mkdir(exist_ok=True)
        (branch / f"file-{index:05d}.txt").write_text("walk", encoding="utf-8")

    rules = make_walk_rules(root)

    started = perf_counter()
    records = [record for batch in walk_batched(root, rules, root_id=1) for record in batch]
    elapsed = perf_counter() - started
    file_count = sum(1 for record in records if not record.is_dir)
    throughput = file_count / elapsed

    print(
        "walk_batched "
        f"files={file_count} elapsed={elapsed:.3f}s throughput={throughput:.0f} files/s "
        f"min_fps={MIN_FILES_PER_SECOND:.0f}"
    )
    assert file_count == FILE_COUNT
    assert throughput >= MIN_FILES_PER_SECOND
