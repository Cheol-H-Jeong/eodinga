from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from time import time

import pytest

from eodinga.common import FileRecord, PathRules
from eodinga.content.base import ParsedContent
from eodinga.index.schema import apply_schema

RUN_PERF = os.getenv("EODINGA_RUN_PERF") == "1"
perf_only = pytest.mark.skipif(not RUN_PERF, reason="set EODINGA_RUN_PERF=1 to run perf tests")


def perf_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = int(raw)
    if value <= 0:
        raise ValueError(f"{name} must be > 0")
    return value


def perf_float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = float(raw)
    if value <= 0:
        raise ValueError(f"{name} must be > 0")
    return value


def open_perf_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    apply_schema(conn)
    return conn


def insert_root(conn: sqlite3.Connection, root: Path) -> None:
    conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        (str(root), "[]", "[]", 1),
    )
    conn.commit()


def make_walk_rules(root: Path) -> PathRules:
    root_text = str(root)
    return PathRules(root=root, include=(root_text, f"{root_text}/**"), exclude=())


def make_file_record(path: Path, root_id: int = 1, size: int = 0) -> FileRecord:
    now = int(time())
    return FileRecord(
        root_id=root_id,
        path=path,
        parent_path=path.parent,
        name=path.name,
        name_lower=path.name.lower(),
        ext=path.suffix.lower().lstrip("."),
        size=size,
        mtime=now,
        ctime=now,
        is_dir=False,
        is_symlink=False,
        indexed_at=now,
    )


def make_parsed(path: Path, token: str) -> ParsedContent:
    return ParsedContent(
        title=path.name,
        head_text=f"head {token}",
        body_text=f"{token} body text for {path.name}",
        content_sha=f"sha-{path.name}-{token}".encode(),
    )
