from __future__ import annotations

from pathlib import Path
from queue import Empty
from threading import Thread
from time import monotonic, sleep

import pytest
from watchdog.events import FileMovedEvent

from eodinga.common import WatchEvent
from eodinga.core.watcher import WatchService, _Handler, _normalize_root
from eodinga.observability import recent_snapshots, reset_metrics, snapshot_metrics


def test_watcher_handler_maps_move_leaving_root_to_delete(tmp_path: Path) -> None:
    service = WatchService()
    root = tmp_path / "watched"
    outside = tmp_path / "outside"
    source = root / "draft.txt"
    destination = outside / "draft.txt"
    handler = _Handler(service, root)

    handler.on_any_event(FileMovedEvent(str(source), str(destination)))
    service._flush_ready(force=True)

    event = service.queue.get_nowait()
    assert event.event_type == "deleted"
    assert event.path == source
    assert event.src_path is None
    assert event.root_path == root


def test_watcher_handler_maps_move_entering_root_to_create(tmp_path: Path) -> None:
    service = WatchService()
    root = tmp_path / "watched"
    outside = tmp_path / "outside"
    source = outside / "draft.txt"
    destination = root / "draft.txt"
    handler = _Handler(service, root)

    handler.on_any_event(FileMovedEvent(str(source), str(destination)))
    service._flush_ready(force=True)

    event = service.queue.get_nowait()
    assert event.event_type == "created"
    assert event.path == destination
    assert event.src_path is None
    assert event.root_path == root


def test_watcher_handler_preserves_move_within_root(tmp_path: Path) -> None:
    service = WatchService()
    root = tmp_path / "watched"
    source = root / "draft.txt"
    destination = root / "report.txt"
    handler = _Handler(service, root)

    handler.on_any_event(FileMovedEvent(str(source), str(destination)))
    service._flush_ready(force=True)

    event = service.queue.get_nowait()
    assert event.event_type == "moved"
    assert event.path == destination
    assert event.src_path == source
    assert event.root_path == root


def test_watcher_handler_normalizes_same_path_move_to_modify(tmp_path: Path) -> None:
    service = WatchService()
    root = tmp_path / "watched"
    target = root / "draft.txt"
    handler = _Handler(service, root)

    handler.on_any_event(FileMovedEvent(str(target), str(target)))
    service._flush_ready(force=True)

    event = service.queue.get_nowait()
    assert event.event_type == "modified"
    assert event.path == target
    assert event.src_path is None
    assert event.root_path == root


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


def test_watcher_move_then_destination_create_preserves_move_metadata(tmp_path: Path) -> None:
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
            event_type="created",
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


def test_watcher_flushed_create_then_move_ignores_late_source_delete(tmp_path: Path) -> None:
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
    service._flush_ready(force=True)

    event = service.queue.get_nowait()
    assert event.event_type == "created"
    assert event.path == destination

    service.record(
        WatchEvent(
            event_type="deleted",
            path=source,
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


def test_watcher_move_round_trip_collapses_to_modify_and_ignores_intermediate_delete(
    tmp_path: Path,
) -> None:
    service = WatchService()
    source = tmp_path / "draft.txt"
    intermediate = tmp_path / "draft-renamed.txt"

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
            path=source,
            src_path=intermediate,
            root_path=tmp_path,
            happened_at=2.0,
        )
    )
    service._flush_ready(force=True)

    event = service.queue.get_nowait()
    assert event.event_type == "modified"
    assert event.path == source
    assert event.src_path is None

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
    reset_metrics()
    service.start(tmp_path)
    service.start(tmp_path)
    service.stop()

    metrics = snapshot_metrics()
    assert started == [tmp_path]
    assert stopped == [tmp_path]
    assert metrics["counters"]["watcher_observers_started"] == 1
    assert metrics["counters"]["watcher_observers_stopped"] == 1


def test_watcher_start_normalizes_equivalent_root_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import eodinga.core.watcher as watcher_module

    started: list[Path] = []

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
            return None

        def join(self, timeout: float | None = None) -> None:
            assert timeout == 1

    monkeypatch.setattr(watcher_module, "Observer", FakeObserver)

    monkeypatch.chdir(tmp_path.parent)
    relative_root = Path(tmp_path.name)
    service = WatchService()

    service.start(relative_root)
    service.start(tmp_path)
    service.stop()

    assert started == [tmp_path]


def test_watcher_normalize_root_preserves_extended_windows_prefix() -> None:
    normalized = _normalize_root(Path(r"\\?\c:\workspace/reports\\"))

    assert normalized == Path(r"\\?\C:\workspace\reports")


def test_watcher_start_normalizes_equivalent_extended_windows_root_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import eodinga.core.watcher as watcher_module

    started: list[Path] = []

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
            return None

        def join(self, timeout: float | None = None) -> None:
            assert timeout == 1

    monkeypatch.setattr(watcher_module, "Observer", FakeObserver)

    service = WatchService()

    service.start(Path(r"\\?\c:\workspace/reports"))
    service.start(Path(r"\\?\C:/workspace/reports\\"))
    service.stop()

    assert started == [Path(r"\\?\C:\workspace\reports")]


@pytest.mark.parametrize("failure_stage", ["schedule", "start"])
def test_watcher_start_cleans_up_flush_thread_after_observer_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure_stage: str
) -> None:
    import eodinga.core.watcher as watcher_module

    lifecycle: list[str] = []

    class FakeObserver:
        def schedule(self, _handler: object, _root_text: str, recursive: bool = True) -> None:
            assert recursive is True
            lifecycle.append("schedule")
            if failure_stage == "schedule":
                raise RuntimeError("simulated schedule failure")

        def start(self) -> None:
            lifecycle.append("start")
            if failure_stage == "start":
                raise RuntimeError("simulated start failure")

        def stop(self) -> None:
            lifecycle.append("stop")

        def join(self, timeout: float | None = None) -> None:
            assert timeout == 1
            lifecycle.append("join")

    monkeypatch.setattr(watcher_module, "Observer", FakeObserver)

    service = WatchService()
    reset_metrics()

    with pytest.raises(RuntimeError, match=f"simulated {failure_stage} failure"):
        service.start(tmp_path)

    metrics = snapshot_metrics()
    assert service._observers == {}
    assert service._flush_thread is None
    assert service._stop.is_set() is True
    assert lifecycle[-2:] == ["stop", "join"]
    assert metrics["counters"]["watcher_observer_failures"] == 1
    assert metrics["counters"][f"watcher_observer_failures.{failure_stage}"] == 1
    assert metrics["counters"]["watcher_startup_rollbacks"] == 1
    assert recent_snapshots()[-1]["payload"] == {
        "root": str(tmp_path),
        "stage": failure_stage,
        "action": "start",
    }


def test_watcher_stop_continues_cleanup_when_observer_teardown_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = WatchService()
    observed: list[str] = []
    reset_metrics()

    class FakeObserver:
        def __init__(self, name: str, *, fail_stop: bool = False, fail_join: bool = False) -> None:
            self.name = name
            self.fail_stop = fail_stop
            self.fail_join = fail_join

        def start(self) -> None:
            observed.append(f"{self.name}:start")

        def stop(self) -> None:
            observed.append(f"{self.name}:stop")
            if self.fail_stop:
                raise RuntimeError(f"{self.name} stop failed")

        def join(self, timeout: float | None = None) -> None:
            assert timeout == 1
            observed.append(f"{self.name}:join")
            if self.fail_join:
                raise RuntimeError(f"{self.name} join failed")

    class FakeThread(Thread):
        def __init__(self) -> None:
            super().__init__(daemon=True)
            self.joined = False

        def is_alive(self) -> bool:
            return True

        def join(self, timeout: float | None = None) -> None:
            assert timeout == 1
            self.joined = True

    messages: list[str] = []

    def record_exception(message: str, *args: object) -> None:
        messages.append(message.format(*args))

    monkeypatch.setattr(service._logger, "exception", record_exception)
    flush_thread = FakeThread()
    service._flush_thread = flush_thread
    service._observers = {
        tmp_path / "one": FakeObserver("one", fail_stop=True, fail_join=True),
        tmp_path / "two": FakeObserver("two"),
    }

    service.stop()

    metrics = snapshot_metrics()
    assert observed == ["one:stop", "two:stop", "one:join", "two:join"]
    assert flush_thread.joined is True
    assert service._observers == {}
    assert service._flush_thread is None
    assert service._stop.is_set() is True
    assert metrics["counters"]["watcher_observer_cleanup_failures"] == 2
    assert metrics["counters"]["watcher_observer_cleanup_failures.stop"] == 1
    assert metrics["counters"]["watcher_observer_cleanup_failures.join"] == 1
    assert [entry["payload"] for entry in recent_snapshots()] == [
        {"root": str(tmp_path / "one"), "stage": "stop", "action": "stop"},
        {"root": str(tmp_path / "one"), "stage": "join", "action": "stop"},
    ]
    assert any("failed stopping watcher observer" in message for message in messages)
    assert any("failed joining watcher observer" in message for message in messages)


def test_watcher_queue_backpressure_blocks_until_consumer_drains(tmp_path: Path) -> None:
    service = WatchService(queue_maxsize=1)
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    finished = False

    service.record(
        WatchEvent(
            event_type="created",
            path=first,
            root_path=tmp_path,
            happened_at=1.0,
        )
    )
    service._flush_ready(force=True)

    def emit_second() -> None:
        nonlocal finished
        service.record(
            WatchEvent(
                event_type="created",
                path=second,
                root_path=tmp_path,
                happened_at=2.0,
            )
        )
        service._flush_ready(force=True)
        finished = True

    thread = Thread(target=emit_second, daemon=True)
    thread.start()
    sleep(0.1)

    assert finished is False

    first_event = service.queue.get_nowait()
    assert first_event.path == first

    thread.join(timeout=1)
    assert finished is True

    second_event = service.queue.get_nowait()
    assert second_event.path == second


def test_watcher_blocked_move_flush_preserves_retired_source_suppression(tmp_path: Path) -> None:
    service = WatchService(queue_maxsize=1)
    occupied = tmp_path / "occupied.txt"
    source = tmp_path / "draft.txt"
    destination = tmp_path / "report.txt"
    finished = False

    service.record(
        WatchEvent(
            event_type="created",
            path=occupied,
            root_path=tmp_path,
            happened_at=1.0,
        )
    )
    service._flush_ready(force=True)

    def emit_move() -> None:
        nonlocal finished
        service.record(
            WatchEvent(
                event_type="moved",
                path=destination,
                src_path=source,
                root_path=tmp_path,
                happened_at=2.0,
            )
        )
        service._flush_ready(force=True)
        finished = True

    thread = Thread(target=emit_move, daemon=True)
    thread.start()
    sleep(0.1)

    assert finished is False

    first_event = service.queue.get_nowait()
    assert first_event.path == occupied

    thread.join(timeout=1)
    assert finished is True

    move_event = service.queue.get_nowait()
    assert move_event.event_type == "moved"
    assert move_event.path == destination
    assert move_event.src_path == source

    service.record(
        WatchEvent(
            event_type="deleted",
            path=source,
            root_path=tmp_path,
            happened_at=3.0,
        )
    )
    service._flush_ready(force=True)

    with pytest.raises(Empty):
        service.queue.get_nowait()
