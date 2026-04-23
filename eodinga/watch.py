from __future__ import annotations

import json
import signal
import threading
from contextlib import AbstractContextManager
from pathlib import Path
from queue import Empty
from stat import S_ISDIR, S_ISLNK
from time import time
from collections.abc import Callable
from typing import Any
from time import sleep

from eodinga.common import FileRecord, PathRules
from eodinga.config import RootConfig
from eodinga.content.registry import parse
from eodinga.core.fs import stat_follow_safe, stat_safe
from eodinga.core.rules import should_index
from eodinga.core.watcher import WatchService
from eodinga.index.writer import IndexWriter

_READY_DELAY_SECONDS = 0.05


class _WatchStop(AbstractContextManager["_WatchStop"]):
    def __init__(self) -> None:
        self._requested = False
        self._received_signal: signal.Signals | None = None
        self._handlers: dict[signal.Signals, Any] = {}
        self._active = False

    def __enter__(self) -> _WatchStop:
        if threading.current_thread() is not threading.main_thread():
            return self
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
        self._requested = True
        self._received_signal = signal.Signals(signum)

    def raise_if_requested(self) -> None:
        if self._requested:
            raise KeyboardInterrupt(self._received_signal or signal.SIGINT)


def _normalize_root(root: RootConfig) -> RootConfig:
    return root.model_copy(update={"path": root.path.expanduser()})


def _ensure_root_rows(conn, roots: list[RootConfig]) -> dict[Path, int]:
    rows = conn.execute("SELECT id, path FROM roots ORDER BY id").fetchall()
    root_ids = {Path(row[1]).expanduser(): int(row[0]) for row in rows}
    next_root_id = max((int(row[0]) for row in rows), default=0) + 1
    for root in roots:
        if root.path in root_ids:
            continue
        conn.execute(
            """
            INSERT INTO roots(id, path, include, exclude, added_at)
            VALUES (?, ?, ?, ?, strftime('%s', 'now'))
            """,
            (
                next_root_id,
                str(root.path),
                json.dumps(root.include),
                json.dumps(root.exclude),
            ),
        )
        root_ids[root.path] = next_root_id
        next_root_id += 1
    conn.commit()
    return {root.path: root_ids[root.path] for root in roots}


def _record_for_path(path: Path, root_id: int) -> FileRecord | None:
    try:
        stat_result = stat_safe(path)
    except OSError:
        return None
    is_symlink = S_ISLNK(stat_result.st_mode)
    is_dir = S_ISDIR(stat_result.st_mode)
    if is_symlink and not is_dir:
        try:
            is_dir = S_ISDIR(stat_follow_safe(path).st_mode)
        except OSError:
            is_dir = False
    return FileRecord(
        root_id=root_id,
        path=path,
        parent_path=path.parent,
        name=path.name,
        name_lower=path.name.lower(),
        ext=path.suffix.lower().lstrip("."),
        size=stat_result.st_size,
        mtime=int(stat_result.st_mtime),
        ctime=int(stat_result.st_ctime),
        is_dir=is_dir,
        is_symlink=is_symlink,
        indexed_at=int(time()),
    )


def watch_index(
    conn,
    roots: list[RootConfig],
    *,
    on_ready: Callable[[], None] | None = None,
) -> None:
    effective_roots = [_normalize_root(root) for root in roots]
    if not effective_roots:
        raise ValueError("watch requires at least one root")

    root_ids = _ensure_root_rows(conn, effective_roots)
    rules_by_root = {
        root.path: PathRules(
            root=root.path,
            include=tuple(root.include),
            exclude=tuple(root.exclude),
        )
        for root in effective_roots
    }
    service = WatchService()
    writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=4096))
    try:
        for root in effective_roots:
            service.start(root.path)
        sleep(_READY_DELAY_SECONDS)
        if on_ready is not None:
            on_ready()
        with _WatchStop() as stop:
            while True:
                stop.raise_if_requested()
                try:
                    event = service.queue.get(timeout=0.05)
                except Empty:
                    continue
                root_path = event.root_path
                if root_path is None or root_path not in root_ids:
                    continue
                rules = rules_by_root[root_path]
                root_id = root_ids[root_path]

                def _load_record(path: Path) -> FileRecord | None:
                    if not should_index(path, rules):
                        return None
                    return _record_for_path(path, root_id)

                writer.apply_events([event], record_loader=_load_record)
    finally:
        service.stop()
