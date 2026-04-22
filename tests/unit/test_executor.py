from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
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
    content_hash: bytes | None = None,
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
            content_hash,
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


def test_execute_relative_date_queries(tmp_db: sqlite3.Connection) -> None:
    today_start = int(datetime.now(tz=UTC).replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    yesterday_start = today_start - 86_400
    this_week_start = today_start - datetime.now(tz=UTC).weekday() * 86_400
    last_month = int((datetime.now(tz=UTC) - timedelta(days=40)).timestamp())

    _insert_file(tmp_db, 1, "/workspace/today.txt", 512, today_start + 60, "txt", body_text="today note")
    _insert_file(
        tmp_db,
        2,
        "/workspace/yesterday.txt",
        1024,
        yesterday_start + 60,
        "txt",
        body_text="yesterday note",
    )
    _insert_file(
        tmp_db,
        3,
        "/workspace/week.txt",
        2048,
        this_week_start + 120,
        "txt",
        body_text="week note",
    )
    _insert_file(
        tmp_db,
        4,
        "/workspace/old.txt",
        4096,
        last_month,
        "txt",
        body_text="old note",
    )
    tmp_db.commit()

    assert search(tmp_db, "date:today", limit=5).hits[0].file.name == "today.txt"
    assert search(tmp_db, "date:yesterday", limit=5).hits[0].file.name == "yesterday.txt"
    this_week_hits = [hit.file.name for hit in search(tmp_db, "date:this-week", limit=10).hits]
    assert "today.txt" in this_week_hits
    assert "yesterday.txt" in this_week_hits
    assert "week.txt" in this_week_hits
    this_month_hits = [hit.file.name for hit in search(tmp_db, "date:this-month", limit=10).hits]
    assert "old.txt" not in this_month_hits


def test_execute_reversed_date_range_query(tmp_db: sqlite3.Connection) -> None:
    jan_1 = int(datetime(2026, 1, 1, 12, tzinfo=UTC).timestamp())
    jan_2 = int(datetime(2026, 1, 2, 12, tzinfo=UTC).timestamp())
    jan_3 = int(datetime(2026, 1, 3, 12, tzinfo=UTC).timestamp())

    _insert_file(tmp_db, 1, "/workspace/jan-1.txt", 512, jan_1, "txt", body_text="jan 1")
    _insert_file(tmp_db, 2, "/workspace/jan-2.txt", 512, jan_2, "txt", body_text="jan 2")
    _insert_file(tmp_db, 3, "/workspace/jan-3.txt", 512, jan_3, "txt", body_text="jan 3")
    tmp_db.commit()

    hits = [
        hit.file.name
        for hit in search(tmp_db, "date:2026-01-03..2026-01-01", limit=10).hits
    ]
    assert hits == ["jan-1.txt", "jan-2.txt", "jan-3.txt"]


def test_execute_duplicate_and_negated_size_queries(tmp_db: sqlite3.Connection) -> None:
    now = 1_713_528_000
    duplicate_hash = b"same-content"

    _insert_file(
        tmp_db,
        1,
        "/workspace/alpha-copy.txt",
        12 * 1024 * 1024,
        now,
        "txt",
        body_text="alpha duplicate one",
        content_hash=duplicate_hash,
    )
    _insert_file(
        tmp_db,
        2,
        "/workspace/alpha-clone.txt",
        11 * 1024 * 1024,
        now - 60,
        "txt",
        body_text="alpha duplicate two",
        content_hash=duplicate_hash,
    )
    _insert_file(
        tmp_db,
        3,
        "/workspace/beta.txt",
        9 * 1024 * 1024,
        now - 120,
        "txt",
        body_text="beta unique",
        content_hash=b"unique-content",
    )
    tmp_db.commit()

    duplicate_hits = [hit.file.name for hit in search(tmp_db, "is:duplicate size:>10M", limit=10).hits]
    assert duplicate_hits == ["alpha-clone.txt", "alpha-copy.txt"]

    unique_hits = [hit.file.name for hit in search(tmp_db, "-is:duplicate -size:>10M", limit=10).hits]
    assert unique_hits == ["beta.txt"]


def test_execute_negated_group_query(tmp_db: sqlite3.Connection) -> None:
    now = 1_713_528_000
    _insert_file(tmp_db, 1, "/workspace/alpha-plan.txt", 1024, now, "txt", body_text="alpha")
    _insert_file(tmp_db, 2, "/workspace/beta-plan.txt", 1024, now - 60, "txt", body_text="beta")
    _insert_file(tmp_db, 3, "/workspace/gamma-plan.txt", 1024, now - 120, "txt", body_text="gamma")
    _insert_file(tmp_db, 4, "/workspace/notes.md", 1024, now - 180, "md", body_text="misc")
    tmp_db.commit()

    hits = [hit.file.name for hit in search(tmp_db, "-(alpha | beta) ext:txt", limit=10).hits]
    assert hits == ["gamma-plan.txt"]


def test_execute_korean_filename_queries(tmp_db: sqlite3.Connection) -> None:
    now = 1_713_528_000
    _insert_file(tmp_db, 1, "/workspace/문서/회의록-봄.txt", 1024, now, "txt", body_text="spring")
    _insert_file(tmp_db, 2, "/workspace/문서/회의록-가을.txt", 1024, now - 60, "txt", body_text="fall")
    _insert_file(tmp_db, 3, "/workspace/문서/영수증.pdf", 1024, now - 120, "pdf", body_text="receipt")
    tmp_db.commit()

    meeting_hits = [hit.file.name for hit in search(tmp_db, "회의록", limit=10).hits]
    assert meeting_hits[:2] == ["회의록-봄.txt", "회의록-가을.txt"]

    receipt_hits = [hit.file.name for hit in search(tmp_db, "문서 영수증", limit=10).hits]
    assert receipt_hits == ["영수증.pdf"]


def test_execute_korean_middle_token_filename_query(tmp_db: sqlite3.Connection) -> None:
    now = 1_713_528_000
    _insert_file(tmp_db, 1, "/workspace/문서함/프로젝트-회의록.txt", 1024, now, "txt", body_text="meeting")
    _insert_file(tmp_db, 2, "/workspace/문서함/회의록모음.txt", 1024, now - 60, "txt", body_text="archive")
    _insert_file(tmp_db, 3, "/workspace/문서함/프로젝트보고서.txt", 1024, now - 120, "txt", body_text="report")
    tmp_db.commit()

    hits = [hit.file.name for hit in search(tmp_db, "회의록", limit=10).hits]
    assert hits == ["회의록모음.txt", "프로젝트-회의록.txt"]


def test_path_queries_use_paths_fts(tmp_db: sqlite3.Connection) -> None:
    now = 1_713_528_000
    _insert_file(tmp_db, 1, "/workspace/projects/report-011.py", 1024, now, "py", body_text="launch")
    _insert_file(tmp_db, 2, "/workspace/archive/report-011.txt", 1024, now - 60, "txt")
    tmp_db.commit()

    statements: list[str] = []
    tmp_db.set_trace_callback(statements.append)
    try:
        hits = [hit.file.name for hit in search(tmp_db, "report-011", limit=10).hits]
    finally:
        tmp_db.set_trace_callback(None)

    assert hits == ["report-011.py", "report-011.txt"]
    assert any("FROM paths_fts" in statement and "MATCH" in statement for statement in statements)


def test_execute_double_negated_group_query(tmp_db: sqlite3.Connection) -> None:
    now = 1_713_528_000
    _insert_file(tmp_db, 1, "/workspace/alpha.txt", 1024, now, "txt", body_text="alpha")
    _insert_file(tmp_db, 2, "/workspace/beta.txt", 1024, now - 60, "txt", body_text="beta")
    _insert_file(tmp_db, 3, "/workspace/gamma.txt", 1024, now - 120, "txt", body_text="gamma")
    tmp_db.commit()

    hits = [hit.file.name for hit in search(tmp_db, "-(-(alpha | beta))", limit=10).hits]
    assert hits == ["alpha.txt", "beta.txt"]
