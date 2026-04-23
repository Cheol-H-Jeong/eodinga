from __future__ import annotations

import json
import signal
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from pathlib import Path
from queue import Empty
from threading import Event
from time import time
from typing import Any, NamedTuple

from eodinga.common import FileRecord, PathRules, WatchEvent
from eodinga.config import RootConfig
from eodinga.core.rules import should_index
from eodinga.core.watcher import WatchService
from eodinga.index.writer import IndexWriter

RecordLoader = Callable[[Path], FileRecord | None]


class WatchRoot(NamedTuple):
    id: int
    path: Path
    rules: PathRules


class _SignalStop(AbstractContextManager["_SignalStop"]):
    def __init__(self) -> None:
        self._requested = Event()
        self._handlers: dict[signal.Signals, Any] = {}
        self._active = False

    def __enter__(self) -> _SignalStop:
        installed: list[signal.Signals] = []
        try:
            for signum in (signal.SIGINT, signal.SIGTERM):
                self._handlers[signum] = signal.getsignal(signum)
                signal.signal(signum, self._handle_signal)
                installed.append(signum)
        except Exception:
            for signum in installed:
                signal.signal(signum, self._handlers[signum])
            self._handlers.clear()
            raise
        self._active = True
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if self._active:
            for signum, handler in self._handlers.items():
                signal.signal(signum, handler)
        return False

    def _handle_signal(self, signum: int, _frame) -> None:
        del signum
        self._requested.set()

    def requested(self) -> bool:
        return self._requested.is_set()


def load_watch_roots(
    conn,
    config_roots: Sequence[RootConfig],
) -> list[WatchRoot]:
    rows = conn.execute(
        "SELECT id, path, include, exclude FROM roots WHERE enabled = 1 ORDER BY id"
    ).fetchall()
    if not rows and config_roots:
        normalized_roots = [
            root.model_copy(update={"path": root.path.expanduser()}) for root in config_roots
        ]
        with conn:
            for root in normalized_roots:
                conn.execute(
                    """
                    INSERT INTO roots(path, include, exclude, enabled, added_at)
                    VALUES (?, ?, ?, 1, strftime('%s', 'now'))
                    ON CONFLICT(path) DO UPDATE SET
                      include=excluded.include,
                      exclude=excluded.exclude,
                      enabled=1
                    """,
                    (
                        str(root.path),
                        json.dumps(root.include),
                        json.dumps(root.exclude),
                    ),
                )
        rows = conn.execute(
            "SELECT id, path, include, exclude FROM roots WHERE enabled = 1 ORDER BY id"
        ).fetchall()
    roots: list[WatchRoot] = []
    for row in rows:
        include = tuple(json.loads(row["include"] or "[]") or ["**/*"])
        exclude = tuple(json.loads(row["exclude"] or "[]"))
        root_path = Path(row["path"])
        roots.append(
            WatchRoot(
                id=int(row["id"]),
                path=root_path,
                rules=PathRules(root=root_path, include=include, exclude=exclude),
            )
        )
    roots.sort(key=lambda root: len(root.path.parts), reverse=True)
    return roots


def make_record_loader(roots: Sequence[WatchRoot]) -> RecordLoader:
    ordered_roots = sorted(roots, key=lambda root: len(root.path.parts), reverse=True)

    def load_record(path: Path) -> FileRecord | None:
        root = _resolve_root(path, ordered_roots)
        if root is None or not should_index(path, root.rules):
            return None
        try:
            stat_result = path.lstat()
        except OSError:
            return None
        return FileRecord(
            root_id=root.id,
            path=path,
            parent_path=path.parent,
            name=path.name,
            name_lower=path.name.lower(),
            ext=path.suffix.lower().lstrip("."),
            size=stat_result.st_size,
            mtime=int(stat_result.st_mtime),
            ctime=int(stat_result.st_ctime),
            is_dir=path.is_dir(),
            is_symlink=path.is_symlink(),
            indexed_at=int(time()),
        )

    return load_record


def run_watch_loop(
    conn,
    *,
    roots: Sequence[WatchRoot],
    writer: IndexWriter,
    service: WatchService | None = None,
    on_ready: Callable[[Sequence[WatchRoot]], None] | None = None,
) -> int:
    if not roots:
        raise ValueError("watch requires at least one indexed root")
    watch_service = service or WatchService()
    record_loader = make_record_loader(roots)
    try:
        for root in roots:
            watch_service.start(root.path)
        with _SignalStop() as stop:
            if on_ready is not None:
                on_ready(roots)
            while not stop.requested():
                events = _read_events(watch_service, timeout=0.1)
                if events:
                    writer.apply_events(events, record_loader=record_loader)
    finally:
        watch_service.stop(clear_queue=False)
        remaining = _drain_events(watch_service)
        if remaining:
            writer.apply_events(remaining, record_loader=record_loader)
    return 0


def _resolve_root(path: Path, roots: Sequence[WatchRoot]) -> WatchRoot | None:
    for root in roots:
        try:
            path.relative_to(root.path)
        except ValueError:
            continue
        return root
    return None


def _read_events(service: WatchService, *, timeout: float) -> list[WatchEvent]:
    try:
        first = service.queue.get(timeout=timeout)
    except Empty:
        return []
    events = [first]
    events.extend(_drain_events(service))
    return events


def _drain_events(service: WatchService) -> list[WatchEvent]:
    events: list[WatchEvent] = []
    while True:
        try:
            events.append(service.queue.get_nowait())
        except Empty:
            return events


__all__ = ["WatchRoot", "load_watch_roots", "make_record_loader", "run_watch_loop"]
