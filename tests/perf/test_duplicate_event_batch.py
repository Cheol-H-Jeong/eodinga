from __future__ import annotations

from pathlib import Path
from time import perf_counter

from eodinga.common import WatchEvent
from eodinga.index.writer import IndexWriter
from tests.conftest import make_record
from tests.perf._helpers import insert_root, open_perf_db, perf_float_env, perf_int_env, perf_only

pytestmark = perf_only

FILE_COUNT = perf_int_env("EODINGA_PERF_DUPLICATE_EVENT_FILE_COUNT", 1_000)
DUPLICATES_PER_FILE = perf_int_env("EODINGA_PERF_DUPLICATE_EVENT_REPEAT", 5)
MIN_EVENTS_PER_SECOND = perf_float_env("EODINGA_PERF_DUPLICATE_EVENT_MIN_EPS", 10_000.0)


def test_duplicate_event_batch_throughput(tmp_path: Path) -> None:
    root = tmp_path / "duplicate-events"
    root.mkdir()
    conn = open_perf_db(tmp_path / "duplicate-events.db")
    try:
        insert_root(conn, root)
        writer = IndexWriter(conn)
        events: list[WatchEvent] = []
        for index in range(FILE_COUNT):
            path = root / f"live-{index:04d}.txt"
            path.write_text(f"live {index}", encoding="utf-8")
            for _ in range(DUPLICATES_PER_FILE):
                events.append(WatchEvent(event_type="modified", path=path))

        started = perf_counter()
        processed = writer.apply_events(events, record_loader=make_record)
        elapsed = perf_counter() - started
        throughput = processed / elapsed
        print(
            "duplicate_event_batch "
            f"events={processed} elapsed={elapsed:.3f}s throughput={throughput:.0f} events/s "
            f"min_eps={MIN_EVENTS_PER_SECOND:.0f}"
        )
        assert processed == FILE_COUNT * DUPLICATES_PER_FILE
        assert conn.execute("SELECT COUNT(*) FROM files").fetchone() == (FILE_COUNT,)
        assert throughput >= MIN_EVENTS_PER_SECOND
    finally:
        conn.close()
