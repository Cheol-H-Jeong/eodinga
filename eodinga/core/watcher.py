from __future__ import annotations

from collections.abc import Callable
from os import fsdecode
from pathlib import Path
from queue import Queue
from threading import Event, Lock, Thread
from time import monotonic
from typing import Protocol

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from eodinga.common import WatchEvent

_DEBOUNCE_SECONDS = 0.1
_FLUSH_LIMIT = 500


def _event_type_for(event: FileSystemEvent) -> str:
    if event.event_type == "moved":
        return "moved"
    if event.event_type == "created":
        return "created"
    if event.event_type == "deleted":
        return "deleted"
    return "modified"


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
        dest_path = Path(fsdecode(event.dest_path)) if event.event_type == "moved" else None
        self._service.record(
            WatchEvent(
                event_type=_event_type_for(event),
                path=dest_path or src_path,
                src_path=src_path if dest_path else None,
                is_dir=event.is_directory,
                root_path=self._root,
                happened_at=monotonic(),
            )
        )


class WatchService:
    def __init__(self) -> None:
        self.queue: Queue[WatchEvent] = Queue()
        self._pending: dict[Path, WatchEvent] = {}
        self._timestamps: dict[Path, float] = {}
        self._lock = Lock()
        self._stop = Event()
        self._flush_thread = None
        self._observers: dict[Path, _ManagedObserver] = {}

    def start(self, root: Path) -> None:
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

    def record(self, event: WatchEvent) -> None:
        with self._lock:
            if event.event_type == "moved" and event.src_path is not None:
                source_existing = self._pending.pop(event.src_path, None)
                self._timestamps.pop(event.src_path, None)
                event = self._merge_move(source_existing, event)
            existing = self._pending.get(event.path)
            if (
                existing is not None
                and existing.event_type == "moved"
                and event.event_type == "deleted"
            ):
                self.queue.put(existing)
                self._pending[event.path] = event
                self._timestamps[event.path] = monotonic()
                return
            merged = self._coalesce(existing, event)
            if merged is None:
                self._pending.pop(event.path, None)
                self._timestamps.pop(event.path, None)
            else:
                self._pending[event.path] = merged
                self._timestamps[event.path] = monotonic()
            if len(self._pending) >= _FLUSH_LIMIT:
                self._flush_ready(force=True)

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
        if new.event_type == "moved":
            return new
        return new

    def _flush_loop(self) -> None:
        while not self._stop.wait(0.05):
            self._flush_ready(force=False)
        self._flush_ready(force=True)

    def _flush_ready(self, force: bool) -> None:
        now = monotonic()
        with self._lock:
            ready_paths = [
                path
                for path, timestamp in self._timestamps.items()
                if force or (now - timestamp) >= _DEBOUNCE_SECONDS
            ]
            for path in ready_paths:
                event = self._pending.pop(path, None)
                self._timestamps.pop(path, None)
                if event is not None:
                    self.queue.put(event)
