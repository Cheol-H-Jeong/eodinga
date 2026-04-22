from __future__ import annotations

from pathlib import Path
from queue import Empty
from time import monotonic, sleep

from eodinga.core.watcher import WatchService


def test_watcher_coalesces_events_within_500ms(tmp_path: Path) -> None:
    service = WatchService()
    service.start(tmp_path)
    try:
        target = tmp_path / "watched.txt"
        renamed = tmp_path / "renamed.txt"
        target.write_text("one", encoding="utf-8")
        target.write_text("two", encoding="utf-8")
        sleep(0.15)
        target.rename(renamed)
        sleep(0.15)
        renamed.unlink()

        seen: list[str] = []
        deadline = monotonic() + 0.5
        while monotonic() < deadline:
            try:
                event = service.queue.get(timeout=0.05)
            except Empty:
                continue
            seen.append(event.event_type)
            if "deleted" in seen and "moved" in seen:
                break
        assert "created" in seen
        assert "moved" in seen
        assert "deleted" in seen
    finally:
        service.stop()
