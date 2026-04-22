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


def test_watcher_chained_move_ignores_intermediate_delete(tmp_path: Path) -> None:
    service = WatchService()
    source = tmp_path / "before.txt"
    intermediate = tmp_path / "middle.txt"
    destination = tmp_path / "after.txt"

    service.record(
        WatchEvent(
            event_type="moved",
            path=intermediate,
            src_path=source,
            root_path=tmp_path,
            happened_at=1.0,
        )
    )
    service.record(
        WatchEvent(
            event_type="moved",
            path=destination,
            src_path=intermediate,
            root_path=tmp_path,
            happened_at=2.0,
        )
    )
    service.record(
        WatchEvent(
            event_type="deleted",
            path=intermediate,
            root_path=tmp_path,
            happened_at=3.0,
        )
    )
    service._flush_ready(force=True)

    event = service.queue.get_nowait()
    assert event.event_type == "moved"
    assert event.path == destination
    assert event.src_path == source

    with pytest.raises(Empty):
        service.queue.get_nowait()


def test_watcher_flushed_move_then_source_delete_stays_suppressed(tmp_path: Path) -> None:
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
    service._flush_ready(force=True)

    event = service.queue.get_nowait()
    assert event.event_type == "moved"
    assert event.path == destination
    assert event.src_path == source

    service.record(
        WatchEvent(
            event_type="deleted",
            path=source,
            root_path=tmp_path,
            happened_at=2.0,
        )
    )
    service._flush_ready(force=True)

    with pytest.raises(Empty):
        service.queue.get_nowait()


def test_watcher_flushed_chained_move_still_ignores_intermediate_delete(tmp_path: Path) -> None:
    service = WatchService()
    source = tmp_path / "before.txt"
    intermediate = tmp_path / "middle.txt"
    destination = tmp_path / "after.txt"

    service.record(
        WatchEvent(
            event_type="moved",
            path=intermediate,
            src_path=source,
            root_path=tmp_path,
            happened_at=1.0,
        )
    )
    service._flush_ready(force=True)

    first = service.queue.get_nowait()
    assert first.event_type == "moved"
    assert first.path == intermediate
    assert first.src_path == source

    service.record(
        WatchEvent(
            event_type="moved",
            path=destination,
            src_path=intermediate,
            root_path=tmp_path,
            happened_at=2.0,
        )
    )
    service._flush_ready(force=True)

    second = service.queue.get_nowait()
    assert second.event_type == "moved"
    assert second.path == destination
    assert second.src_path == intermediate

    service.record(
        WatchEvent(
            event_type="deleted",
            path=intermediate,
            root_path=tmp_path,
            happened_at=3.0,
        )
    )
    service._flush_ready(force=True)

    with pytest.raises(Empty):
        service.queue.get_nowait()


def test_watcher_reused_source_path_delete_coalesces_new_entry(tmp_path: Path) -> None:
    service = WatchService()
    source = tmp_path / "draft.txt"
    backup = tmp_path / "draft.bak"

    service.record(
        WatchEvent(
            event_type="moved",
            path=backup,
            src_path=source,
            root_path=tmp_path,
            happened_at=1.0,
        )
    )
    service.record(
        WatchEvent(
            event_type="created",
            path=source,
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
    assert event.event_type == "moved"
    assert event.path == backup
    assert event.src_path == source

    with pytest.raises(Empty):
        service.queue.get_nowait()


def test_watcher_reused_source_path_modify_then_delete_keeps_real_delete(tmp_path: Path) -> None:
    service = WatchService()
    source = tmp_path / "draft.txt"
    backup = tmp_path / "draft.bak"

    service.record(
        WatchEvent(
            event_type="moved",
            path=backup,
            src_path=source,
            root_path=tmp_path,
            happened_at=1.0,
        )
    )
    service.record(
        WatchEvent(
            event_type="modified",
            path=source,
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
    assert event.event_type == "moved"
    assert event.path == backup
    assert event.src_path == source

    event = service.queue.get_nowait()
    assert event.event_type == "deleted"
    assert event.path == source

    with pytest.raises(Empty):
        service.queue.get_nowait()


def test_watcher_can_restart_after_stop(tmp_path: Path) -> None:
    service = WatchService()
    service.start(tmp_path)
    service.stop()

    service.start(tmp_path)
    try:
        target = tmp_path / "restarted.txt"
        target.write_text("hello", encoding="utf-8")
        sleep(0.3)

        event = service.queue.get(timeout=0.2)
        assert event.event_type == "created"
        assert event.path == target
    finally:
        service.stop()


def test_watcher_stop_clears_stale_pending_events_before_restart(tmp_path: Path) -> None:
    service = WatchService()
    stale = tmp_path / "stale.txt"
    fresh = tmp_path / "fresh.txt"

    service.record(
        WatchEvent(
            event_type="created",
            path=stale,
            root_path=tmp_path,
            happened_at=1.0,
        )
    )
    service.stop()

    service.start(tmp_path)
    try:
        service.record(
            WatchEvent(
                event_type="created",
                path=fresh,
                root_path=tmp_path,
                happened_at=2.0,
            )
        )
        service._flush_ready(force=True)

        event = service.queue.get_nowait()
        assert event.event_type == "created"
        assert event.path == fresh

        with pytest.raises(Empty):
            service.queue.get_nowait()
    finally:
        service.stop()


def test_watcher_start_ignores_duplicate_root_registration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import eodinga.core.watcher as watcher_module

    started: list[Path] = []
    stopped: list[Path] = []

    class FakeObserver:
        def __init__(self) -> None:
            self.root: Path | None = None

        def schedule(self, _handler: object, root_text: str, recursive: bool = True) -> None:
            assert recursive is True
            self.root = Path(root_text)

        def start(self) -> None:
            assert self.root is not None
            started.append(self.root)

        def stop(self) -> None:
            assert self.root is not None
            stopped.append(self.root)

        def join(self, timeout: float | None = None) -> None:
            assert timeout == 1

    monkeypatch.setattr(watcher_module, "Observer", FakeObserver)

    service = WatchService()
    service.start(tmp_path)
    service.start(tmp_path)
    service.stop()

    assert started == [tmp_path]
    assert stopped == [tmp_path]
