from __future__ import annotations

import sqlite3

import pytest


def _insert_file(
    conn: sqlite3.Connection,
    file_id: int,
    path: str,
    body_text: str = "",
) -> None:
    mtime = 1_713_528_000 - file_id
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
            path,
            "/workspace",
            path.rsplit("/", 1)[-1],
            path.rsplit("/", 1)[-1].lower(),
            "txt",
            512,
            mtime,
            mtime,
            0,
            0,
            None,
            mtime,
        ),
    )
    conn.execute(
        "INSERT INTO paths_fts(rowid, name, parent_path, path) VALUES (?, ?, ?, ?)",
        (file_id, path.rsplit("/", 1)[-1], "/workspace", path),
    )
    if body_text:
        conn.execute(
            "INSERT INTO content_fts(rowid, title, head_text, body_text) VALUES (?, ?, ?, ?)",
            (file_id, path.rsplit("/", 1)[-1], body_text[:80], body_text),
        )
        conn.execute(
            """
            INSERT INTO content_map(file_id, fts_rowid, parser, parsed_at, content_sha)
            VALUES (?, ?, ?, ?, ?)
            """,
            (file_id, file_id, "text", mtime, f"sha-{file_id}".encode()),
        )


@pytest.fixture
def boolean_logic_db(tmp_db: sqlite3.Connection) -> sqlite3.Connection:
    for file_id, name in enumerate(
        (
            "alpha.txt",
            "beta.txt",
            "gamma.txt",
            "alpha-beta.txt",
            "alpha-gamma.txt",
            "beta-gamma.txt",
            "alpha-beta-gamma.txt",
        ),
        start=1,
    ):
        _insert_file(tmp_db, file_id, f"/workspace/{name}")
    tmp_db.commit()
    return tmp_db


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("alpha beta", {"alpha-beta.txt", "alpha-beta-gamma.txt"}),
        (
            "alpha | beta",
            {
                "alpha.txt",
                "beta.txt",
                "alpha-beta.txt",
                "alpha-gamma.txt",
                "beta-gamma.txt",
                "alpha-beta-gamma.txt",
            },
        ),
        ("-(alpha | beta)", {"gamma.txt"}),
        ("alpha -beta", {"alpha.txt", "alpha-gamma.txt"}),
        (
            "alpha | (beta gamma)",
            {
                "alpha.txt",
                "alpha-beta.txt",
                "alpha-gamma.txt",
                "beta-gamma.txt",
                "alpha-beta-gamma.txt",
            },
        ),
        ("-(alpha beta) gamma", {"gamma.txt", "alpha-gamma.txt", "beta-gamma.txt"}),
    ],
)
def test_execute_boolean_truth_table(
    boolean_logic_db: sqlite3.Connection,
    query: str,
    expected: set[str],
) -> None:
    from eodinga.query import search

    hits = {hit.file.name for hit in search(boolean_logic_db, query, limit=20).hits}

    assert hits == expected
