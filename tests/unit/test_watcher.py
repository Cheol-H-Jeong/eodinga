from __future__ import annotations

from pathlib import Path
from queue import Empty
from time import monotonic, sleep

import pytest

from eodinga.common import WatchEvent
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


def test_watcher_create_then_move_coalesces_to_destination_path(tmp_path: Path) -> None:
    service = WatchService()
    service.start(tmp_path)
    try:
        source = tmp_path / "draft.txt"
        destination = tmp_path / "report.txt"

        source.write_text("draft", encoding="utf-8")
        source.rename(destination)
        sleep(0.3)

        seen: list[WatchEvent] = []
        deadline = monotonic() + 0.5
        while monotonic() < deadline:
            try:
                seen.append(service.queue.get(timeout=0.05))
            except Empty:
                continue

        assert [(event.event_type, event.path.name) for event in seen] == [("created", "report.txt")]
        assert seen[0].src_path is None
    finally:
        service.stop()


def test_watcher_create_then_move_ignores_late_source_delete(tmp_path: Path) -> None:
    service = WatchService()
    source = tmp_path / "draft.txt"
    destination = tmp_path / "report.txt"

    service.record(
        WatchEvent(
            event_type="created",
            path=source,
            root_path=tmp_path,
            happened_at=1.0,
        )
    )
    service.record(
        WatchEvent(
            event_type="moved",
            path=destination,
            src_path=source,
            root_path=tmp_path,
            happened_at=2.0,
        )
    )
    service.record(
        WatchEvent(
            event_type="deleted",
            path=source,
            root_path=tmp_path,
            happened_at=3.0,
        )
    )
    service._flush_ready(force=True)

    event = service.queue.get_nowait()
    assert event.event_type == "created"
    assert event.path == destination

    with pytest.raises(Empty):
        service.queue.get_nowait()


def test_watcher_move_then_modify_preserves_move_metadata(tmp_path: Path) -> None:
    service = WatchService()
    source = tmp_path / "before.txt"
    destination = tmp_path / "after.txt"

    service.record(
        WatchEvent(
            event_type="moved",
            path=destination,
            src_path=source,
            root_path=tmp_path,
            happened_at=1.0,
        )
    )
    service.record(
        WatchEvent(
            event_type="modified",
            path=destination,
            root_path=tmp_path,
            happened_at=2.0,
        )
    )
    service._flush_ready(force=True)

    event = service.queue.get_nowait()
    assert event.event_type == "moved"
    assert event.path == destination
    assert event.src_path == source


def test_watcher_move_then_source_delete_keeps_single_move_event(tmp_path: Path) -> None:
    service = WatchService()
    source = tmp_path / "before.txt"
    destination = tmp_path / "after.txt"

    service.record(
        WatchEvent(
            event_type="moved",
            path=destination,
            src_path=source,
            root_path=tmp_path,
            happened_at=1.0,
        )
    )
    service.record(
        WatchEvent(
            event_type="deleted",
            path=source,
            root_path=tmp_path,
            happened_at=2.0,
        )
    )
    service._flush_ready(force=True)

    event = service.queue.get_nowait()
    assert event.event_type == "moved"
    assert event.path == destination
    assert event.src_path == source

    with pytest.raises(Empty):
        service.queue.get_nowait()
