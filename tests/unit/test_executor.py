from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from eodinga.query import search


def _insert_file(
    conn: sqlite3.Connection,
    file_id: int,
    path: str,
    size: int,
    mtime: int,
    ext: str,
    body_text: str = "",
    is_dir: int = 0,
) -> None:
    path_obj = Path(path)
    conn.execute(
        """
        INSERT INTO files (
          id, root_id, path, parent_path, name, name_lower, ext, size, mtime, ctime,
          is_dir, is_symlink, content_hash, indexed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            file_id,
            1,
            str(path_obj),
            str(path_obj.parent),
            path_obj.name,
            path_obj.name.lower(),
            ext,
            size,
            mtime,
            mtime,
            is_dir,
            0,
            None,
            mtime,
        ),
    )
    conn.execute(
        "INSERT INTO paths_fts(rowid, name, parent_path, path) VALUES (?, ?, ?, ?)",
        (file_id, path_obj.name, str(path_obj.parent), str(path_obj)),
    )
    if body_text:
        conn.execute(
            "INSERT INTO content_fts(rowid, title, head_text, body_text) VALUES (?, ?, ?, ?)",
            (file_id, path_obj.name, body_text[:80], body_text),
        )
        conn.execute(
            """
            INSERT INTO content_map(file_id, fts_rowid, parser, parsed_at, content_sha)
            VALUES (?, ?, ?, ?, ?)
            """,
            (file_id, file_id, "text", mtime, f"sha-{file_id}".encode()),
        )


@pytest.fixture
def populated_db(tmp_db: sqlite3.Connection) -> sqlite3.Connection:
    now = 1_713_528_000
    for index in range(1, 201):
        ext = "pdf" if index % 5 == 0 else "txt" if index % 3 == 0 else "py"
        folder = "node_modules" if index % 17 == 0 else "projects"
        path = f"/workspace/{folder}/doc-{index:03d}.{ext}"
        body = f"alpha project {index}" if index % 4 == 0 else f"notes beta {index}"
        if index % 9 == 0:
            body += " launch checklist"
        if index % 11 == 0:
            path = f"/workspace/projects/report-{index:03d}.{ext}"
        _insert_file(
            tmp_db,
            index,
            path,
            size=index * 1024,
            mtime=now - index * 3600,
            ext=ext,
            body_text=body,
        )
    tmp_db.commit()
    return tmp_db


@pytest.mark.parametrize(
    ("query", "expected_first"),
    [
        ("doc-001", "doc-001.py"),
        ("report-055 ext:pdf", "report-055.pdf"),
        ("ext:txt", "doc-003.txt"),
        ("size:>150K", "doc-151.py"),
        ("content:launch", "doc-009.txt"),
        ('content:"alpha project 20"', "doc-020.pdf"),
        ("path:projects report-011", "report-011.py"),
        ("/report-[0-9]+/", "report-011.py"),
        ("content:launch -path:node_modules", "doc-009.txt"),
        ('content:"notes beta 1" | content:"alpha project 4"', "doc-001.py"),
        ("report | doc-002", "doc-002.py"),
        ("is:file ext:py", "doc-001.py"),
        ("modified:2024-04-19", "doc-001.py"),
        ("content:/launch checklist/", "doc-009.txt"),
        ("case:false DOC-001", "doc-001.py"),
        ("path:report -ext:pdf", "report-011.py"),
        ('content:"notes beta 7"', "doc-007.py"),
        ("path:/workspace/projects ext:pdf", "doc-005.pdf"),
        ("report-011 -content:launch", "report-011.py"),
        ("doc-034", "doc-034.py"),
    ],
)
def test_execute_queries(populated_db: sqlite3.Connection, query: str, expected_first: str) -> None:
    result = search(populated_db, query, limit=20)
    assert result.hits
    assert result.hits[0].file.name == expected_first


def test_node_modules_are_deboosted(populated_db: sqlite3.Connection) -> None:
    preferred = search(populated_db, "doc-017 | doc-018", limit=10)
    assert preferred.hits[0].file.name == "doc-018.txt"


def test_content_snippet_is_present(populated_db: sqlite3.Connection) -> None:
    result = search(populated_db, "content:launch", limit=5)
    assert result.hits[0].snippet is not None
    assert "launch" in result.hits[0].snippet.lower()
