from __future__ import annotations

import json
import signal
import threading
from contextlib import AbstractContextManager
from pathlib import Path
from time import perf_counter
from typing import Any, NamedTuple

from eodinga.common import PathRules
from eodinga.config import RootConfig
from eodinga.content.registry import parse
from eodinga.core.walker import walk_batched
from eodinga.index.storage import (
    _cleanup_index_files,
    atomic_replace_index,
    connect_database,
    temporary_pragmas,
)
from eodinga.index.writer import IndexWriter
from eodinga.observability import increment_counter, record_histogram

DEFAULT_MAX_BODY_CHARS = 4096
_BULK_WRITE_PRAGMAS = {"synchronous": "NORMAL", "cache_size": -128000}


class RebuildResult(NamedTuple):
    db_path: Path
    files_indexed: int
    roots_indexed: int


class _SignalStop(AbstractContextManager["_SignalStop"]):
    def __init__(self) -> None:
        self._requested = False
        self._received_signal: signal.Signals | None = None
        self._handlers: dict[signal.Signals, Any] = {}
        self._active = False

    def __enter__(self) -> _SignalStop:
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
        pending_signal = None
        if exc_type is None and self._requested:
            pending_signal = (
                signal.SIGINT if self._received_signal is None else self._received_signal
            )
        if self._active:
            for signum, handler in self._handlers.items():
                signal.signal(signum, handler)
        self._active = False
        self._handlers.clear()
        if pending_signal is not None:
            raise KeyboardInterrupt(pending_signal)
        return False

    def _handle_signal(self, signum: int, _frame) -> None:
        self._requested = True
        self._received_signal = signal.Signals(signum)

    def raise_if_requested(self) -> None:
        if self._requested:
            signum = signal.SIGINT if self._received_signal is None else self._received_signal
            raise KeyboardInterrupt(signum)


def _staged_build_path(db_path: Path) -> Path:
    return db_path.with_name(f".{db_path.name}.next")


def _normalize_root(root: RootConfig) -> RootConfig:
    return root.model_copy(update={"path": root.path.expanduser()})


def _insert_roots(conn, roots: list[RootConfig]) -> None:
    rows = [
        (
            root_id,
            str(root.path),
            json.dumps(root.include),
            json.dumps(root.exclude),
        )
        for root_id, root in enumerate(roots, start=1)
    ]
    with conn:
        conn.executemany(
            """
            INSERT INTO roots(id, path, include, exclude, added_at)
            VALUES (?, ?, ?, ?, strftime('%s', 'now'))
            """,
            rows,
        )


def rebuild_index(
    db_path: Path,
    roots: list[RootConfig],
    *,
    content_enabled: bool = True,
    max_body_chars: int = DEFAULT_MAX_BODY_CHARS,
) -> RebuildResult:
    started = perf_counter()
    effective_roots = [_normalize_root(root) for root in roots]
    if not effective_roots:
        raise ValueError("index rebuild requires at least one root")

    target_path = db_path.expanduser()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    staged_path = _staged_build_path(target_path)
    _cleanup_index_files(staged_path)

    conn = connect_database(staged_path)
    files_indexed = 0
    parser_callback = (
        (lambda path: parse(path, max_body_chars=max_body_chars))
        if content_enabled
        else (lambda _path: None)
    )
    try:
        writer = IndexWriter(conn, parser_callback=parser_callback)
        _insert_roots(conn, effective_roots)
        with temporary_pragmas(conn, _BULK_WRITE_PRAGMAS):
            with _SignalStop() as stop:
                for root_id, root in enumerate(effective_roots, start=1):
                    stop.raise_if_requested()
                    rules = PathRules(
                        root=root.path,
                        include=tuple(root.include),
                        exclude=tuple(root.exclude),
                    )
                    for batch in walk_batched(root.path, rules, root_id=root_id):
                        stop.raise_if_requested()
                        indexed = writer.bulk_upsert(batch)
                        if batch:
                            record_histogram(
                                "index_batch_size",
                                float(len(batch)),
                                root=str(root.path),
                            )
                        files_indexed += indexed
                        if indexed:
                            increment_counter("files_indexed", indexed, root=str(root.path))
                        stop.raise_if_requested()
                stop.raise_if_requested()
    except KeyboardInterrupt:
        conn.close()
        raise
    except Exception:
        conn.close()
        _cleanup_index_files(staged_path)
        raise
    conn.close()
    try:
        atomic_replace_index(staged_path, target_path)
    except Exception:
        _cleanup_index_files(staged_path)
        raise
    elapsed_ms = (perf_counter() - started) * 1000
    increment_counter("index_rebuilds_completed")
    record_histogram(
        "index_rebuild_latency_ms",
        elapsed_ms,
        roots_indexed=len(effective_roots),
        content_enabled=content_enabled,
    )
    return RebuildResult(
        db_path=target_path,
        files_indexed=files_indexed,
        roots_indexed=len(effective_roots),
    )


__all__ = ["DEFAULT_MAX_BODY_CHARS", "RebuildResult", "rebuild_index"]
