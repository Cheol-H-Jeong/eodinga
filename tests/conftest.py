from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path
from time import time

import pytest

from eodinga.common import FileRecord
from eodinga.index.migrations import migrate


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "index.db"
    conn = sqlite3.connect(db_path)
    migrate(conn)
    conn.close()
    return db_path


@pytest.fixture()
def sample_tree(tmp_path: Path) -> Callable[[str], Path]:
    def factory(name: str = "workspace") -> Path:
        root = tmp_path / name
        (root / "docs").mkdir(parents=True)
        (root / "code").mkdir()
        (root / ".git").mkdir()
        (root / "node_modules").mkdir()
        (root / "docs" / "guide.md").write_text("# guide\nhello", encoding="utf-8")
        (root / "docs" / "report.txt").write_text("report", encoding="utf-8")
        (root / "code" / "main.py").write_text("print('x')\n", encoding="utf-8")
        (root / ".git" / "config").write_text("[core]\n", encoding="utf-8")
        (root / "node_modules" / "pkg.js").write_text("module.exports = 1;\n", encoding="utf-8")
        return root

    return factory


def make_record(path: Path, root_id: int = 1, indexed_at: int | None = None) -> FileRecord:
    stat_result = path.stat(follow_symlinks=False)
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
        is_dir=path.is_dir(),
        is_symlink=path.is_symlink(),
        indexed_at=indexed_at or int(time()),
    )
