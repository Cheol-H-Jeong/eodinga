from __future__ import annotations

from collections import deque
from collections.abc import Iterator
from typing import NamedTuple
from pathlib import Path
from os import stat_result
from stat import S_ISDIR, S_ISLNK
from time import time

from eodinga.common import FileRecord, PathRules
from eodinga.core.fs import resolve_safe, scandir_entries_safe, stat_follow_safe, stat_safe
from eodinga.core.rules import should_index

BATCH_SIZE = 8192


class _QueuedPath(NamedTuple):
    path: Path
    stat_result: stat_result | None = None


def _to_record(root_id: int, path: Path, stat_result: stat_result) -> FileRecord:
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


def _should_descend(path: Path, root: Path, stat_result: stat_result) -> bool:
    if S_ISDIR(stat_result.st_mode) and not S_ISLNK(stat_result.st_mode):
        return True
    if path != root or not S_ISLNK(stat_result.st_mode):
        return False
    try:
        return resolve_safe(path).is_dir()
    except OSError:
        return False


def _scandir_children(path: Path) -> Iterator[_QueuedPath]:
    for entry in scandir_entries_safe(path):
        try:
            entry_stat = entry.stat(follow_symlinks=False)
        except OSError:
            continue
        yield _QueuedPath(Path(entry.path), entry_stat)


def walk_batched(root: Path, rules: PathRules, root_id: int = 0) -> Iterator[list[FileRecord]]:
    queue: deque[_QueuedPath] = deque([_QueuedPath(root)])
    visited_dirs: set[tuple[int, int]] = set()
    visited_resolved_dirs: set[Path] = set()
    batch: list[FileRecord] = []
    while queue:
        current = queue.popleft()
        current_path = current.path
        current_stat = current.stat_result
        if current_stat is None:
            try:
                current_stat = stat_safe(current_path)
            except OSError:
                continue
        if not should_index(current_path, rules):
            continue
        batch.append(_to_record(root_id=root_id, path=current_path, stat_result=current_stat))
        if len(batch) >= BATCH_SIZE:
            yield batch
            batch = []
        if not _should_descend(current_path, root, current_stat):
            continue
        inode_key = (current_stat.st_dev, current_stat.st_ino)
        if inode_key in visited_dirs:
            continue
        try:
            resolved_dir = resolve_safe(current_path)
        except OSError:
            continue
        if resolved_dir in visited_resolved_dirs:
            continue
        visited_dirs.add(inode_key)
        visited_resolved_dirs.add(resolved_dir)
        try:
            children = _scandir_children(current_path)
        except OSError:
            continue
        queue.extend(children)
    if batch:
        yield batch
