from __future__ import annotations

import builtins
import os
from pathlib import Path
from queue import Empty

import pytest

from eodinga.common import PathRules, WatchEvent
from eodinga.content.registry import parse
from eodinga.core.walker import walk_batched
from eodinga.core.watcher import WatchService
from eodinga.index import open_index
from eodinga.index.writer import IndexWriter
from eodinga.query import search
from tests.conftest import make_record


def _is_write_mode(mode: str) -> bool:
    return any(flag in mode for flag in ("w", "a", "+", "x"))


def _is_write_flags(flags: int) -> bool:
    write_mask = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC
    return bool(flags & write_mask)


def _path_under_root(candidate: object, root: Path) -> Path | None:
    if isinstance(candidate, int):
        return None
    try:
        resolved = Path(os.fspath(candidate))
    except TypeError:
        return None
    return resolved if resolved.is_relative_to(root) else None


def test_runtime_never_writes_user_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    user_root = tmp_path / "user-root"
    docs = user_root / "docs"
    docs.mkdir(parents=True)
    target = docs / "guide.txt"
    target.write_text("guide body\nlauncher query\n", encoding="utf-8")

    db_path = tmp_path / "database" / "index.db"
    conn = open_index(db_path)
    try:
        conn.execute(
            "INSERT INTO roots(id, path, include, exclude, added_at) VALUES (?, ?, ?, ?, ?)",
            (1, str(user_root), "[]", "[]", 1),
        )
        conn.commit()

        original_open = Path.open
        original_builtin_open = builtins.open
        original_os_open = os.open
        attempted_writes: list[tuple[Path, str]] = []

        def guarded_open(
            self: Path,
            mode: str = "r",
            buffering: int = -1,
            encoding: str | None = None,
            errors: str | None = None,
            newline: str | None = None,
        ):
            if self.is_relative_to(user_root) and _is_write_mode(mode):
                attempted_writes.append((self, mode))
                raise AssertionError(f"unexpected write under user root: {self} [{mode}]")
            return original_open(
                self,
                mode=mode,
                buffering=buffering,
                encoding=encoding,
                errors=errors,
                newline=newline,
            )

        def guarded_builtin_open(
            file: object,
            mode: str = "r",
            buffering: int = -1,
            encoding: str | None = None,
            errors: str | None = None,
            newline: str | None = None,
            closefd: bool = True,
            opener=None,
        ):
            path = _path_under_root(file, user_root)
            if path is not None and _is_write_mode(mode):
                attempted_writes.append((path, mode))
                raise AssertionError(f"unexpected write under user root: {path} [{mode}]")
            return original_builtin_open(
                file,
                mode=mode,
                buffering=buffering,
                encoding=encoding,
                errors=errors,
                newline=newline,
                closefd=closefd,
                opener=opener,
            )

        def guarded_os_open(
            path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
            flags: int,
            mode: int = 0o777,
            *,
            dir_fd: int | None = None,
        ) -> int:
            root_path = _path_under_root(path, user_root)
            if root_path is not None and _is_write_flags(flags):
                attempted_writes.append((root_path, f"os.open:{flags}"))
                raise AssertionError(f"unexpected os.open write under user root: {root_path} [{flags}]")
            return original_os_open(path, flags, mode, dir_fd=dir_fd)

        monkeypatch.setattr(Path, "open", guarded_open)
        monkeypatch.setattr(builtins, "open", guarded_builtin_open)
        monkeypatch.setattr(os, "open", guarded_os_open)

        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        records = [
            record
            for batch in walk_batched(user_root, PathRules(root=user_root), root_id=1)
            for record in batch
        ]
        assert writer.bulk_upsert(records) == len(records)

        service = WatchService()
        service.record(WatchEvent(event_type="modified", path=target, root_path=user_root))
        service._flush_ready(force=True)
        event = service.queue.get_nowait()
        assert writer.apply_events([event], record_loader=make_record) == 1

        result = search(conn, "launcher", limit=5)
        names = [hit.file.name for hit in result.hits]
        assert "guide.txt" in names
        assert attempted_writes == []

        with pytest.raises(Empty):
            service.queue.get_nowait()
    finally:
        conn.close()
