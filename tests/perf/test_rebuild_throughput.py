from __future__ import annotations

from pathlib import Path
from time import perf_counter

from eodinga.config import RootConfig
from eodinga.index.build import rebuild_index
from tests.perf._helpers import perf_float_env, perf_int_env, perf_only

pytestmark = perf_only

FILE_COUNT = perf_int_env("EODINGA_PERF_REBUILD_FILE_COUNT", 30_000)
MIN_RECORDS_PER_SECOND = perf_float_env("EODINGA_PERF_REBUILD_MIN_RPS", 12_000.0)


def _populate_tree(root: Path) -> int:
    root.mkdir()
    created = 0
    for index in range(FILE_COUNT):
        branch = root / f"group-{index % 256:03d}"
        branch.mkdir(exist_ok=True)
        (branch / f"file-{index:05d}.txt").touch()
        created += 1
    return created


def test_rebuild_index_throughput(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    created = _populate_tree(root)
    db_path = tmp_path / "index.db"

    started = perf_counter()
    result = rebuild_index(
        db_path,
        [RootConfig(path=root)],
        content_enabled=False,
    )
    elapsed = perf_counter() - started
    throughput = result.files_indexed / elapsed

    print(
        "rebuild_index "
        f"records={result.files_indexed} elapsed={elapsed:.3f}s "
        f"throughput={throughput:.0f} records/s min_rps={MIN_RECORDS_PER_SECOND:.0f}"
    )
    assert result.files_indexed == created + 257
    assert throughput >= MIN_RECORDS_PER_SECOND
