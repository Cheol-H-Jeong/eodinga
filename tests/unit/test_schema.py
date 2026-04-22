from __future__ import annotations

import sqlite3

from eodinga.index.schema import apply_schema, current_schema_version


def test_schema_apply_and_fts_triggers_and_cascade() -> None:
    conn = sqlite3.connect(":memory:")
    apply_schema(conn)
    assert current_schema_version(conn) == 1

    conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        ("/root", "[]", "[]", 1),
    )
    rows = [
        (
            1,
            f"/root/file-{index}.txt",
            "/root",
            f"file-{index}.txt",
            f"file-{index}.txt",
            "txt",
            index,
            1,
            1,
            0,
            0,
            None,
            1,
        )
        for index in range(10)
    ]
    conn.executemany(
        """
        INSERT INTO files(
          root_id, path, parent_path, name, name_lower, ext, size, mtime, ctime,
          is_dir, is_symlink, content_hash, indexed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    assert conn.execute("SELECT COUNT(*) FROM paths_fts").fetchone()[0] == 10

    conn.execute(
        "INSERT INTO content_fts(rowid, title, head_text, body_text) "
        "VALUES (1, 't', 'h', 'b')"
    )
    conn.execute(
        "INSERT INTO content_map(file_id, fts_rowid, parser, parsed_at, content_sha) "
        "VALUES (1, 1, 'stub', 1, X'01')"
    )
    conn.execute("DELETE FROM files WHERE id = 1")
    assert conn.execute("SELECT COUNT(*) FROM content_map WHERE file_id = 1").fetchone()[0] == 0

    conn.execute(
        """
        INSERT INTO files(
          root_id, path, parent_path, name, name_lower, ext, size, mtime, ctime,
          is_dir, is_symlink, content_hash, indexed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(path) DO UPDATE SET indexed_at = excluded.indexed_at
        """,
        (1, "/root/file-2.txt", "/root", "file-2.txt", "file-2.txt", "txt", 2, 1, 1, 0, 0, None, 2),
    )
    file_count = conn.execute(
        "SELECT COUNT(*) FROM files WHERE path = '/root/file-2.txt'"
    ).fetchone()[0]
    fts_count = conn.execute(
        "SELECT COUNT(*) FROM paths_fts WHERE path = '/root/file-2.txt'"
    ).fetchone()[0]
    assert file_count == 1
    assert fts_count == 1
