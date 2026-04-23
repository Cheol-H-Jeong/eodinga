from __future__ import annotations

from pathlib import Path
from time import perf_counter

from eodinga.common import WatchEvent
from eodinga.index.writer import IndexWriter
from tests.perf._helpers import (
    insert_root,
    make_file_record,
    open_perf_db,
    perf_float_env,
    perf_int_env,
    perf_only,
)

pytestmark = perf_only

FILE_COUNT = perf_int_env("EODINGA_PERF_APPLY_EVENTS_FILE_COUNT", 10_000)
MIN_EVENTS_PER_SECOND = perf_float_env("EODINGA_PERF_APPLY_EVENTS_MIN_EPS", 8_000.0)


def test_apply_events_throughput(tmp_path: Path) -> None:
    root = tmp_path / "apply-events"
    root.mkdir()
    conn = open_perf_db(tmp_path / "apply-events.db")
    try:
        insert_root(conn, root)
        writer = IndexWriter(conn)
        records = {
            path: make_file_record(path, size=index)
            for index in range(FILE_COUNT)
            for path in [root / f"live-{index:05d}.txt"]
        }
        events = [WatchEvent(event_type="created", path=path) for path in records]

        started = perf_counter()
        processed = writer.apply_events(events, record_loader=records.get)
        elapsed = perf_counter() - started
        throughput = processed / elapsed
        print(
            "apply_events "
            f"events={processed} elapsed={elapsed:.3f}s throughput={throughput:.0f} events/s "
            f"min_eps={MIN_EVENTS_PER_SECOND:.0f}"
        )
        assert processed == FILE_COUNT
        assert throughput >= MIN_EVENTS_PER_SECOND
    finally:
        conn.close()
