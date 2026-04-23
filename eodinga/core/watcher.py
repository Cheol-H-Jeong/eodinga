from __future__ import annotations

from collections.abc import Callable
from os import fsdecode
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event, Lock, Thread
from time import monotonic
from typing import Protocol

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from eodinga.common import WatchEvent
from eodinga.observability import get_logger, increment_counter, record_histogram

_DEBOUNCE_SECONDS = 0.1
_FLUSH_LIMIT = 500
_QUEUE_PUT_TIMEOUT_SECONDS = 0.05
_DEFAULT_QUEUE_MAXSIZE = 2048


def _event_type_for(event: FileSystemEvent) -> str:
    if event.event_type == "moved":
        return "moved"
    if event.event_type == "created":
        return "created"
    if event.event_type == "deleted":
        return "deleted"
    return "modified"


def _is_within_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


class _ManagedObserver(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def join(self, timeout: float | None = None) -> None: ...


def _spawn_thread(target: Callable[[], None]) -> Thread:
    return Thread(target=target, daemon=True)


class _Handler(FileSystemEventHandler):
    def __init__(self, service: WatchService, root: Path) -> None:
        self._service = service
        self._root = root

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        src_path = Path(fsdecode(event.src_path))
        if event.event_type == "moved":
            dest_path = Path(fsdecode(event.dest_path))
            src_in_root = _is_within_root(src_path, self._root)
            dest_in_root = _is_within_root(dest_path, self._root)
            if src_in_root and dest_in_root:
                normalized = WatchEvent(
                    event_type="moved",
                    path=dest_path,
                    src_path=src_path,
                    is_dir=event.is_directory,
                    root_path=self._root,
                    happened_at=monotonic(),
                )
            elif src_in_root:
                normalized = WatchEvent(
                    event_type="deleted",
                    path=src_path,
                    is_dir=event.is_directory,
                    root_path=self._root,
                    happened_at=monotonic(),
                )
            elif dest_in_root:
                normalized = WatchEvent(
                    event_type="created",
                    path=dest_path,
                    is_dir=event.is_directory,
                    root_path=self._root,
                    happened_at=monotonic(),
                )
            else:
                return
            self._service.record(normalized)
            return
        self._service.record(
            WatchEvent(
                event_type=_event_type_for(event),
                path=src_path,
                is_dir=event.is_directory,
                root_path=self._root,
                happened_at=monotonic(),
            )
        )


class WatchService:
    def __init__(self, *, queue_maxsize: int = _DEFAULT_QUEUE_MAXSIZE) -> None:
        self.queue: Queue[WatchEvent] = Queue(maxsize=max(1, queue_maxsize))
        self._pending: dict[Path, WatchEvent] = {}
        self._retired_sources: dict[Path, set[Path]] = {}
        self._flushed_retired_sources: set[Path] = set()
        self._timestamps: dict[Path, float] = {}
        self._lock = Lock()
        self._stop = Event()
        self._flush_thread = None
        self._observers: dict[Path, _ManagedObserver] = {}
        self._logger = get_logger("core.watcher")

    def start(self, root: Path) -> None:
        if root in self._observers:
            return
        if self._stop.is_set():
            self._stop = Event()
        if self._flush_thread is None or not self._flush_thread.is_alive():
            self._flush_thread = _spawn_thread(self._flush_loop)
            self._flush_thread.start()
        observer = Observer()
        observer.schedule(_Handler(self, root), str(root), recursive=True)
        observer.start()
        self._observers[root] = observer

    def stop(self) -> None:
        self._stop.set()
        for observer in self._observers.values():
            observer.stop()
        for observer in self._observers.values():
            observer.join(timeout=1)
        if self._flush_thread is not None and self._flush_thread.is_alive():
            self._flush_thread.join(timeout=1)
        self._flush_thread = None
        self._observers.clear()
        self._reset_state()

    def record(self, event: WatchEvent) -> None:
        increment_counter("watcher_events", event_type=event.event_type)
        immediate_emit: WatchEvent | None = None
        flush_now = False
        with self._lock:
            if event.event_type in {"created", "modified"}:
                self._flushed_retired_sources.discard(event.path)
            existing = self._pending.get(event.path)
            moved_retired_sources: set[Path] = set()
            if event.event_type == "moved" and event.src_path is not None:
                source_existing = self._pending.pop(event.src_path, None)
                moved_retired_sources = self._retired_sources.pop(event.src_path, set())
                self._flushed_retired_sources.discard(event.path)
                self._flushed_retired_sources.discard(event.src_path)
                self._timestamps.pop(event.src_path, None)
                if source_existing is not None and source_existing.event_type in {"created", "moved"}:
                    moved_retired_sources.add(event.src_path)
                event = self._merge_move(source_existing, event)
                existing = self._pending.get(event.path)
            if event.event_type == "deleted" and existing is None and self._is_retired_move_source(event.path):
                return
            if (
                existing is not None
                and existing.event_type == "moved"
                and event.event_type == "deleted"
            ):
                immediate_emit = existing
                self._pending[event.path] = event
                self._timestamps[event.path] = monotonic()
            else:
                merged = self._coalesce(existing, event)
                if merged is None:
                    self._pending.pop(event.path, None)
                    self._retired_sources.pop(event.path, None)
                    self._timestamps.pop(event.path, None)
                else:
                    self._pending[event.path] = merged
                    if moved_retired_sources:
                        moved_retired_sources.update(self._retired_sources.get(event.path, set()))
                        self._retired_sources[event.path] = moved_retired_sources
                    self._timestamps[event.path] = monotonic()
                flush_now = len(self._pending) >= _FLUSH_LIMIT
        if immediate_emit is not None:
            self._enqueue_event(immediate_emit)
            return
        if flush_now:
            self._flush_ready(force=True)

    def _is_retired_move_source(self, path: Path) -> bool:
        return any(
            pending.event_type == "moved" and pending.src_path == path
            for pending in self._pending.values()
        ) or any(path in retired_sources for retired_sources in self._retired_sources.values()) or (
            path in self._flushed_retired_sources
        )

    def _merge_move(self, existing: WatchEvent | None, moved: WatchEvent) -> WatchEvent:
        if existing is None:
            return moved
        if existing.event_type == "created":
            return WatchEvent(
                event_type="created",
                path=moved.path,
                root_path=moved.root_path,
                happened_at=moved.happened_at,
            )
        if existing.event_type == "moved":
            if existing.src_path == moved.path:
                return WatchEvent(
                    event_type="modified",
                    path=moved.path,
                    root_path=moved.root_path,
                    happened_at=moved.happened_at,
                )
            return WatchEvent(
                event_type="moved",
                path=moved.path,
                src_path=existing.src_path,
                root_path=moved.root_path,
                happened_at=moved.happened_at,
            )
        return moved

    def _coalesce(self, existing: WatchEvent | None, new: WatchEvent) -> WatchEvent | None:
        if existing is None:
            return new
        if existing.event_type == "created" and new.event_type == "modified":
            return existing
        if existing.event_type == "created" and new.event_type == "deleted":
            return None
        if existing.event_type == "modified" and new.event_type == "deleted":
            return WatchEvent(
                event_type="deleted",
                path=new.path,
                src_path=existing.src_path,
                root_path=new.root_path,
                happened_at=new.happened_at,
            )
        if existing.event_type == "moved" and new.event_type == "modified":
            return WatchEvent(
                event_type="moved",
                path=existing.path,
                src_path=existing.src_path,
                root_path=new.root_path,
                happened_at=new.happened_at,
            )
        if existing.event_type == "moved" and new.event_type == "created":
            return WatchEvent(
                event_type="moved",
                path=existing.path,
                src_path=existing.src_path,
                root_path=new.root_path,
                happened_at=new.happened_at,
            )
        if new.event_type == "moved":
            return new
        return new

    def _flush_loop(self) -> None:
        while not self._stop.wait(0.05):
            self._flush_ready(force=False)
        self._flush_ready(force=True)

    def _flush_ready(self, force: bool) -> None:
        now = monotonic()
        flushed: list[WatchEvent] = []
        with self._lock:
            ready_paths = [
                path
                for path, timestamp in self._timestamps.items()
                if force or (now - timestamp) >= _DEBOUNCE_SECONDS
            ]
            for path in ready_paths:
                event = self._pending.pop(path, None)
                retired_sources = self._retired_sources.pop(path, set())
                self._timestamps.pop(path, None)
                if event is not None:
                    if event.event_type == "moved" and event.src_path is not None:
                        retired_sources = {event.src_path, *retired_sources}
                    if retired_sources:
                        self._flushed_retired_sources.update(retired_sources)
                    if event.event_type in {"created", "modified", "deleted"}:
                        self._flushed_retired_sources.discard(event.path)
                    flushed.append(event)
        delivered: list[WatchEvent] = []
        for event in flushed:
            if not self._enqueue_event(event):
                with self._lock:
                    self._pending[event.path] = event
                    self._timestamps[event.path] = now
                break
            delivered.append(event)
        if delivered:
            increment_counter("watcher_flushes")
            increment_counter("watcher_events_flushed", len(delivered))
            record_histogram("watch_flush_batch_size", float(len(delivered)))
            for event in delivered:
                lag_ms = max((now - event.happened_at) * 1000, 0.0)
                record_histogram("watch_event_lag_ms", lag_ms, event_type=event.event_type)

    def _reset_state(self) -> None:
        with self._lock:
            self._pending.clear()
            self._retired_sources.clear()
            self._flushed_retired_sources.clear()
            self._timestamps.clear()
        while True:
            try:
                self.queue.get_nowait()
            except Empty:
                break

    def _enqueue_event(self, event: WatchEvent) -> bool:
        blocked_at: float | None = None
        while not self._stop.is_set():
            try:
                self.queue.put(event, timeout=_QUEUE_PUT_TIMEOUT_SECONDS)
                if blocked_at is not None:
                    record_histogram(
                        "watcher_queue_backpressure_ms",
                        (monotonic() - blocked_at) * 1000,
                        event_type=event.event_type,
                    )
                return True
            except Full:
                if blocked_at is None:
                    blocked_at = monotonic()
                    increment_counter("watcher_queue_full", event_type=event.event_type)
                    self._logger.warning(
                        "watch queue full; applying backpressure for {}", event.path
                    )
        increment_counter("watcher_enqueue_aborted", event_type=event.event_type)
        return False
