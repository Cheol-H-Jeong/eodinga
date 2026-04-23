from __future__ import annotations

import json
import signal
from pathlib import Path
from threading import current_thread, main_thread
from types import FrameType
from typing import NamedTuple, cast

from eodinga.common import PathRules
from eodinga.config import RootConfig
from eodinga.content.registry import parse
from eodinga.core.walker import walk_batched
from eodinga.index.storage import _cleanup_index_files, atomic_replace_index, connect_database
from eodinga.index.writer import IndexWriter
from eodinga.observability import increment_counter

DEFAULT_MAX_BODY_CHARS = 4096


class RebuildResult(NamedTuple):
    db_path: Path
    files_indexed: int
    roots_indexed: int


class RebuildInterrupted(KeyboardInterrupt):
    def __init__(self, signum: signal.Signals) -> None:
        self.signum = signum
        super().__init__(f"index rebuild interrupted by {signum.name}")


class _DeferredSignalInterrupt:
    def __init__(self) -> None:
        self._previous: dict[signal.Signals, object] = {}
        self._received: signal.Signals | None = None
        self._enabled = False

    def __enter__(self) -> _DeferredSignalInterrupt:
        if current_thread() is not main_thread():
            return self
        for signum in (signal.SIGINT, signal.SIGTERM):
            self._previous[signum] = signal.getsignal(signum)
            signal.signal(signum, self._handle)
        self._enabled = True
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if not self._enabled:
            return
        for signum, handler in self._previous.items():
            signal.signal(signum, cast(signal.Handlers, handler))
        self._previous.clear()
        self._enabled = False

    def _handle(self, signum: int, _frame: FrameType | None) -> None:
        if self._received is None:
            self._received = signal.Signals(signum)

    def raise_if_requested(self) -> None:
        if self._received is not None:
            raise RebuildInterrupted(self._received)


def _staged_build_path(db_path: Path) -> Path:
    return db_path.with_name(f".{db_path.name}.next")


def _normalize_root(root: RootConfig) -> RootConfig:
    return root.model_copy(update={"path": root.path.expanduser()})


def rebuild_index(
    db_path: Path,
    roots: list[RootConfig],
    *,
    content_enabled: bool = True,
    max_body_chars: int = DEFAULT_MAX_BODY_CHARS,
) -> RebuildResult:
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
        with _DeferredSignalInterrupt() as interrupts:
            for root_id, root in enumerate(effective_roots, start=1):
                with conn:
                    conn.execute(
                        """
                        INSERT INTO roots(id, path, include, exclude, added_at)
                        VALUES (?, ?, ?, ?, strftime('%s', 'now'))
                        """,
                        (
                            root_id,
                            str(root.path),
                            json.dumps(root.include),
                            json.dumps(root.exclude),
                        ),
                    )
                interrupts.raise_if_requested()
                rules = PathRules(
                    root=root.path,
                    include=tuple(root.include),
                    exclude=tuple(root.exclude),
                )
                for batch in walk_batched(root.path, rules, root_id=root_id):
                    indexed = writer.bulk_upsert(batch)
                    files_indexed += indexed
                    if indexed:
                        increment_counter("files_indexed", indexed, root=str(root.path))
                    interrupts.raise_if_requested()
    except BaseException:
        conn.close()
        _cleanup_index_files(staged_path)
        raise
    conn.close()
    try:
        atomic_replace_index(staged_path, target_path)
    except Exception:
        _cleanup_index_files(staged_path)
        raise
    return RebuildResult(
        db_path=target_path,
        files_indexed=files_indexed,
        roots_indexed=len(effective_roots),
    )


__all__ = ["DEFAULT_MAX_BODY_CHARS", "RebuildResult", "rebuild_index"]
