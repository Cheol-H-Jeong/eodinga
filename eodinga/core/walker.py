from __future__ import annotations

from collections import deque
from collections.abc import Iterator
from pathlib import Path
from stat import S_ISDIR, S_ISLNK
from time import time

from eodinga.common import FileRecord, PathRules
from eodinga.core.fs import resolve_safe, scandir_safe, stat_safe
from eodinga.core.rules import should_index

BATCH_SIZE = 8192


def _to_record(root_id: int, path: Path) -> FileRecord:
    stat_result = stat_safe(path)
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
        is_dir=S_ISDIR(stat_result.st_mode),
        is_symlink=S_ISLNK(stat_result.st_mode),
        indexed_at=int(time()),
    )


def walk_batched(root: Path, rules: PathRules, root_id: int = 0) -> Iterator[list[FileRecord]]:
    queue: deque[Path] = deque([resolve_safe(root)])
    visited: set[tuple[int, int]] = set()
    batch: list[FileRecord] = []
    while queue:
        current = queue.popleft()
        try:
            stat_result = stat_safe(current)
        except OSError:
            continue
        inode_key = (stat_result.st_dev, stat_result.st_ino)
        if inode_key in visited:
            continue
        visited.add(inode_key)
        if not should_index(current, rules):
            continue
        batch.append(_to_record(root_id=root_id, path=current))
        if len(batch) >= BATCH_SIZE:
            yield batch
            batch = []
        if S_ISDIR(stat_result.st_mode) and not S_ISLNK(stat_result.st_mode):
            try:
                children = sorted(scandir_safe(current), key=lambda item: item.name)
            except OSError:
                continue
            queue.extend(children)
    if batch:
        yield batch
