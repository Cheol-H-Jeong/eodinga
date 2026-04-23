from __future__ import annotations

from collections import deque
from collections.abc import Iterator
from pathlib import Path
from os import stat_result
from stat import S_ISDIR, S_ISLNK
from time import time
from typing import NamedTuple

from eodinga.common import FileRecord, PathRules
from eodinga.core.fs import ScanEntry, resolve_safe, scandir_safe, stat_follow_safe, stat_safe
from eodinga.core.rules import should_index

BATCH_SIZE = 8192


class WalkTarget(NamedTuple):
    path: Path
    stat_result: stat_result | None = None
    needs_resolve: bool = False


def _to_record(root_id: int, path: Path, stat_result: stat_result, indexed_at: int) -> FileRecord:
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
        indexed_at=indexed_at,
    )


def _should_descend(path: Path, root: Path, stat_result: stat_result, *, is_dir: bool) -> bool:
    if is_dir and not S_ISLNK(stat_result.st_mode):
        return True
    return path == root and S_ISLNK(stat_result.st_mode) and is_dir


def _queue_target(target: Path | ScanEntry, *, needs_resolve: bool) -> WalkTarget:
    if isinstance(target, ScanEntry):
        return WalkTarget(
            path=target.path,
            stat_result=target.stat_result,
            needs_resolve=needs_resolve,
        )
    return WalkTarget(path=target, needs_resolve=needs_resolve)


def walk_batched(root: Path, rules: PathRules, root_id: int = 0) -> Iterator[list[FileRecord]]:
    queue: deque[WalkTarget] = deque([WalkTarget(path=root, needs_resolve=True)])
    visited_dirs: set[tuple[int, int]] = set()
    visited_resolved_dirs: set[Path] = set()
    batch: list[FileRecord] = []
    indexed_at = int(time())
    while queue:
        current = queue.popleft()
        current_path = current.path
        cached_stat = current.stat_result
        try:
            current_stat = cached_stat if cached_stat is not None else stat_safe(current_path)
        except OSError:
            continue
        if not should_index(current_path, rules):
            continue
        record = _to_record(
            root_id=root_id,
            path=current_path,
            stat_result=current_stat,
            indexed_at=indexed_at,
        )
        batch.append(record)
        if len(batch) >= BATCH_SIZE:
            yield batch
            batch = []
            indexed_at = int(time())
        if not _should_descend(
            current_path,
            root,
            current_stat,
            is_dir=record.is_dir,
        ):
            continue
        inode_key = (current_stat.st_dev, current_stat.st_ino)
        if inode_key in visited_dirs:
            continue
        needs_resolve = current.needs_resolve or S_ISLNK(current_stat.st_mode)
        if needs_resolve:
            try:
                resolved_dir = resolve_safe(current_path)
            except OSError:
                continue
        else:
            resolved_dir = current_path
        resolve_descendants = S_ISLNK(current_stat.st_mode) or (
            current.needs_resolve and resolved_dir != current_path
        )
        if resolved_dir in visited_resolved_dirs:
            continue
        visited_dirs.add(inode_key)
        visited_resolved_dirs.add(resolved_dir)
        try:
            children = scandir_safe(current_path)
        except OSError:
            continue
        queue.extend(
            _queue_target(child, needs_resolve=resolve_descendants) for child in children
        )
    if batch:
        yield batch
