from __future__ import annotations

import signal
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from threading import current_thread, main_thread
from typing import Any, NamedTuple, cast

from eodinga.common import PathRules
from eodinga.config import RootConfig
from eodinga.content.registry import parse
from eodinga.core.walker import walk_batched
from eodinga.index.storage import _cleanup_index_files, atomic_replace_index
from eodinga.index.writer import IndexWriter

DEFAULT_MAX_BODY_CHARS = 4096


class RebuildResult(NamedTuple):
    db_path: Path
    files_indexed: int
    roots_indexed: int


class RebuildInterrupted(RuntimeError):
    def __init__(self, signum: int) -> None:
        self.signum = signum
        super().__init__(f"index rebuild interrupted by signal {signum}")


class _InterruptController:
    def __init__(self) -> None:
        self.signum: int | None = None

    def request(self, signum: int) -> None:
        if self.signum is None:
            self.signum = signum

    def raise_if_requested(self) -> None:
        if self.signum is not None:
            raise RebuildInterrupted(self.signum)


def _staged_build_path(db_path: Path) -> Path:
    return db_path.with_name(f".{db_path.name}.next")


def _normalize_root(root: RootConfig) -> RootConfig:
    return root.model_copy(update={"path": root.path.expanduser()})


@contextmanager
def _rebuild_interrupts():
    controller = _InterruptController()
    if current_thread() is not main_thread():
        yield controller
        return

    handled_signals = [signal.SIGINT]
    if hasattr(signal, "SIGTERM"):
        handled_signals.append(signal.SIGTERM)

    previous_handlers: dict[signal.Signals, Any] = {}

    def _handle(signum: int, _frame) -> None:
        controller.request(signum)

    try:
        for signum in handled_signals:
            previous_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, _handle)
        yield controller
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, cast(Any, handler))


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

    conn = sqlite3.connect(staged_path)
    files_indexed = 0
    parser_callback = (
        (lambda path: parse(path, max_body_chars=max_body_chars))
        if content_enabled
        else (lambda _path: None)
    )
    try:
        writer = IndexWriter(conn, parser_callback=parser_callback)
        with _rebuild_interrupts() as interrupts:
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
                    files_indexed += writer.bulk_upsert(batch)
                    interrupts.raise_if_requested()
            interrupts.raise_if_requested()
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
    return RebuildResult(
        db_path=target_path,
        files_indexed=files_indexed,
        roots_indexed=len(effective_roots),
    )


__all__ = ["DEFAULT_MAX_BODY_CHARS", "RebuildResult", "rebuild_index"]
