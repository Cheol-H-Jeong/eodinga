from __future__ import annotations

from pathlib import Path
from queue import Empty
from time import monotonic, sleep

from eodinga.core.watcher import WatchService
from eodinga.index.reader import find_by_path
from eodinga.index.writer import IndexWriter
from tests.conftest import make_record
from tests.perf._helpers import insert_root, open_perf_db, perf_only

pytestmark = perf_only

FILE_COUNT = 25
P99_LIMIT_SECONDS = 2.0


def test_watch_update_visibility_latency(tmp_path: Path) -> None:
    root = tmp_path / "watched"
    root.mkdir()
    conn = open_perf_db(tmp_path / "watch-latency.db")
    insert_root(conn, root)
    writer = IndexWriter(conn)
    service = WatchService()
    service.start(root)
    latencies: list[float] = []
    try:
        for index in range(FILE_COUNT):
            path = root / f"live-{index:02d}.txt"
            started = monotonic()
            path.write_text(f"live {index}", encoding="utf-8")
            deadline = monotonic() + 2.0
            while monotonic() < deadline:
                try:
                    event = service.queue.get(timeout=0.05)
                except Empty:
                    continue
                writer.apply_events([event], record_loader=make_record)
                if find_by_path(conn, path) is not None:
                    latencies.append(monotonic() - started)
                    break
            else:
                raise AssertionError(f"{path} did not become query-visible in time")
            sleep(0.02)

        latencies.sort()
        p99_index = max(0, int(len(latencies) * 0.99) - 1)
        p99 = latencies[p99_index]
        print(f"watch_latency count={len(latencies)} p99={p99:.3f}s")
        assert p99 <= P99_LIMIT_SECONDS
    finally:
        service.stop()
        conn.close()
