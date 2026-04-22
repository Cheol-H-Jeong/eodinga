from __future__ import annotations

from pathlib import Path
from time import perf_counter

from eodinga.common import PathRules
from eodinga.core.walker import walk_batched
from eodinga.index.reader import stats
from eodinga.index.writer import IndexWriter
from tests.perf._helpers import insert_root, open_perf_db, perf_only

pytestmark = perf_only

FILE_COUNT = 20_000
MIN_FILES_PER_SECOND = 7_000.0


def test_cold_start_throughput(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    root.mkdir()
    for index in range(FILE_COUNT):
        branch = root / f"dir-{index % 200:03d}"
        branch.mkdir(exist_ok=True)
        (branch / f"file-{index:05d}.txt").touch()

    conn = open_perf_db(tmp_path / "cold-start.db")
    try:
        insert_root(conn, root)
        writer = IndexWriter(conn)

        started = perf_counter()
        inserted = 0
        for batch in walk_batched(root, PathRules(root=root), root_id=1):
            inserted += writer.bulk_upsert(batch)
        elapsed = perf_counter() - started

        snapshot = stats(conn)
        throughput = inserted / elapsed
        print(
            f"cold_start files={inserted} elapsed={elapsed:.3f}s throughput={throughput:.0f} files/s"
        )
        assert snapshot.file_count == inserted
        assert throughput >= MIN_FILES_PER_SECOND
    finally:
        conn.close()
