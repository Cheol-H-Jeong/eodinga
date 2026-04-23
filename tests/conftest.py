from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from collections.abc import Callable
from collections.abc import Iterator
from collections.abc import Mapping
from collections.abc import Sequence
from pathlib import Path
from time import time
from typing import cast

import pytest
from PySide6.QtWidgets import QApplication

from eodinga.common import FileRecord
from eodinga.index.schema import apply_schema


class TempDb:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        apply_schema(self._conn)

    def __fspath__(self) -> str:
        return str(self.path)

    def execute(
        self,
        sql: str,
        parameters: Sequence[object] | Mapping[str, object] = (),
        /,
    ) -> sqlite3.Cursor:
        if "INSERT INTO files" in sql:
            self._conn.execute(
                "INSERT INTO roots(id, path, include, exclude, added_at) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO NOTHING",
                (1, "/workspace", "[]", "[]", 1),
            )
        return self._conn.execute(sql, parameters)

    def __getattr__(self, name: str):
        return getattr(self._conn, name)

    def close(self) -> None:
        self._conn.close()


def make_record(path: Path, root_id: int = 1) -> FileRecord:
    stat_result = path.lstat()
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
        indexed_at=int(time()),
    )


@pytest.fixture()
def temp_config_path(tmp_path: Path) -> Path:
    return tmp_path / "config.toml"


@pytest.fixture()
def cli_runner(tmp_path: Path) -> Iterator[Callable[..., subprocess.CompletedProcess[str]]]:
    def run(*args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.setdefault("QT_QPA_PLATFORM", "offscreen")
        env.setdefault("EODINGA_METRICS_PATH", str(tmp_path / "metrics.json"))
        env.setdefault("EODINGA_DISABLE_FILE_LOGGING", "1")
        return subprocess.run(
            [sys.executable, "-m", "eodinga", *args],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    yield run


@pytest.fixture()
def parse_json_output() -> Callable[[str], dict[str, object]]:
    def parse(output: str) -> dict[str, object]:
        return json.loads(output)

    return parse


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Iterator[TempDb]:
    db = TempDb(tmp_path / "index.db")
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def sample_tree(tmp_path: Path) -> Callable[[], Path]:
    def build() -> Path:
        root = tmp_path / "sample-tree"
        docs = root / "docs"
        src = root / "src"
        docs.mkdir(parents=True)
        src.mkdir(parents=True)
        (docs / "guide.md").write_text("# Guide\n", encoding="utf-8")
        (docs / "notes.txt").write_text("hello\n", encoding="utf-8")
        (src / "main.py").write_text("print('hi')\n", encoding="utf-8")
        return root

    return build


@pytest.fixture()
def qapp() -> Iterator[QApplication]:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = cast(QApplication, QApplication.instance() or QApplication([]))
    yield app


@pytest.fixture()
def parser_fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures" / "parsers"
