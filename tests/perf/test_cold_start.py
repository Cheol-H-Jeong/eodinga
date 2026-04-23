from __future__ import annotations

from pathlib import Path
from time import perf_counter

from eodinga.config import RootConfig
from eodinga.core.walker import walk_batched
from eodinga.index.build import rebuild_index
from eodinga.index.reader import stats
from eodinga.index.storage import open_index
from eodinga.index.writer import IndexWriter
from tests.perf._helpers import (
    insert_root,
    make_walk_rules,
    open_perf_db,
    perf_float_env,
    perf_int_env,
    perf_only,
)

pytestmark = perf_only

FILE_COUNT = perf_int_env("EODINGA_PERF_COLD_START_FILE_COUNT", 20_000)
MIN_FILES_PER_SECOND = perf_float_env("EODINGA_PERF_COLD_START_MIN_FPS", 4_000.0)
REBUILD_MIN_FILES_PER_SECOND = perf_float_env("EODINGA_PERF_REBUILD_MIN_FPS", 3_500.0)


def _populate_tree(root: Path) -> int:
    file_count = 0
    root.mkdir()
    for index in range(FILE_COUNT):
        branch = root / f"dir-{index % 200:03d}"
        branch.mkdir(exist_ok=True)
        (branch / f"file-{index:05d}.txt").touch()
        file_count += 1
    return file_count


def test_cold_start_throughput(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    created = _populate_tree(root)

    conn = open_perf_db(tmp_path / "cold-start.db", bulk_writes=True)
    try:
        insert_root(conn, root)
        writer = IndexWriter(conn)

        started = perf_counter()
        inserted = 0
        for batch in walk_batched(root, make_walk_rules(root), root_id=1):
            inserted += writer.bulk_upsert(batch)
        elapsed = perf_counter() - started

        snapshot = stats(conn)
        throughput = inserted / elapsed
        print(
            "cold_start "
            f"files={inserted} elapsed={elapsed:.3f}s throughput={throughput:.0f} files/s "
            f"min_fps={MIN_FILES_PER_SECOND:.0f}"
        )
        assert created == FILE_COUNT
        assert snapshot.file_count == inserted
        assert throughput >= MIN_FILES_PER_SECOND
    finally:
        conn.close()


def test_rebuild_cold_start_throughput(tmp_path: Path) -> None:
    root = tmp_path / "rebuild-tree"
    created = _populate_tree(root)
    db_path = tmp_path / "rebuild-index.db"

    started = perf_counter()
    result = rebuild_index(db_path, [RootConfig(path=root)], content_enabled=False)
    elapsed = perf_counter() - started

    conn = open_index(db_path)
    try:
        snapshot = stats(conn)
    finally:
        conn.close()

    throughput = result.files_indexed / elapsed
    print(
        "rebuild_cold_start "
        f"files={result.files_indexed} elapsed={elapsed:.3f}s throughput={throughput:.0f} files/s "
        f"min_fps={REBUILD_MIN_FILES_PER_SECOND:.0f}"
    )
    assert created == FILE_COUNT
    assert snapshot.file_count == result.files_indexed
    assert throughput >= REBUILD_MIN_FILES_PER_SECOND
