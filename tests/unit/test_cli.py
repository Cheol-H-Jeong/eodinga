from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from eodinga import __version__
from eodinga.index.schema import apply_schema


def _insert_file(
    conn: sqlite3.Connection,
    file_id: int,
    path: str,
    size: int,
    mtime: int,
    ext: str,
    *,
    body_text: str = "",
    content_hash: bytes | None = None,
) -> None:
    path_obj = Path(path)
    conn.execute(
        "INSERT INTO roots(id, path, include, exclude, added_at) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(id) DO NOTHING",
        (1, "/workspace", "[]", "[]", 1),
    )
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
            0,
            0,
            content_hash,
            mtime,
        ),
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


def _build_search_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        apply_schema(conn)
        duplicate_hash = b"same-content"
        today_start = int(
            datetime.now(tz=UTC).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        )
        yesterday_start = today_start - int(timedelta(days=1).total_seconds())
        _insert_file(
            conn,
            1,
            "/workspace/reports/today-alpha-copy.txt",
            12 * 1024 * 1024,
            today_start + 60,
            "txt",
            body_text="alpha duplicate launch note",
            content_hash=duplicate_hash,
        )
        _insert_file(
            conn,
            2,
            "/workspace/reports/today-alpha-clone.txt",
            11 * 1024 * 1024,
            today_start + 120,
            "txt",
            body_text="alpha duplicate launch note",
            content_hash=duplicate_hash,
        )
        _insert_file(
            conn,
            3,
            "/workspace/archive/yesterday-beta.txt",
            9 * 1024 * 1024,
            yesterday_start + 60,
            "txt",
            body_text="beta archive note",
            content_hash=b"unique-content",
        )
        conn.commit()
    finally:
        conn.close()


def test_all_subcommands_help_succeed(cli_runner) -> None:
    for command in ("index", "watch", "search", "stats", "gui", "doctor", "version"):
        result = cli_runner(command, "--help")
        assert result.returncode == 0
        assert "usage:" in result.stdout.lower()


def test_search_json_returns_json(cli_runner) -> None:
    result = cli_runner("search", "needle", "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["query"] == "needle"
    assert isinstance(payload["results"], list)


def test_search_json_queries_real_index(cli_runner, tmp_path: Path) -> None:
    db_path = tmp_path / "index.db"
    _build_search_db(db_path)

    result = cli_runner(
        "--db",
        str(db_path),
        "search",
        "date:today size:>10M is:duplicate -path:archive",
        "--json",
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert [Path(item["path"]).name for item in payload["results"]] == [
        "today-alpha-clone.txt",
        "today-alpha-copy.txt",
    ]


def test_search_json_honors_root_filter(cli_runner, tmp_path: Path) -> None:
    db_path = tmp_path / "index.db"
    _build_search_db(db_path)

    result = cli_runner(
        "--db",
        str(db_path),
        "search",
        "duplicate",
        "--json",
        "--root",
        "/workspace/reports",
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert [Path(item["path"]).parent.name for item in payload["results"]] == ["reports", "reports"]


def test_search_json_root_filter_pushes_scope_into_query(cli_runner, tmp_path: Path) -> None:
    db_path = tmp_path / "index.db"
    conn = sqlite3.connect(db_path)
    try:
        apply_schema(conn)
        conn.execute(
            "INSERT INTO roots(id, path, include, exclude, added_at) VALUES (?, ?, ?, ?, ?)",
            (1, "/workspace", "[]", "[]", 1),
        )
        for file_id in range(1, 61):
            _insert_file(
                conn,
                file_id,
                f"/workspace/other/alpha-{file_id:03d}.txt",
                1024,
                1_713_528_000 - file_id,
                "txt",
                body_text="alpha outside root",
            )
        _insert_file(
            conn,
            999,
            "/workspace/reports/alpha-target.txt",
            1024,
            1_713_528_000,
            "txt",
            body_text="alpha inside scoped root",
        )
        conn.commit()
    finally:
        conn.close()

    result = cli_runner(
        "--db",
        str(db_path),
        "search",
        "alpha",
        "--json",
        "--limit",
        "1",
        "--root",
        "/workspace/reports",
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert [Path(item["path"]).name for item in payload["results"]] == ["alpha-target.txt"]


def test_search_reports_invalid_query_cleanly(cli_runner, tmp_path: Path) -> None:
    db_path = tmp_path / "index.db"
    _build_search_db(db_path)

    result = cli_runner("--db", str(db_path), "search", "content:", "--json")

    assert result.returncode == 2
    assert "expected operator value" in result.stderr


def test_version_matches_package(cli_runner) -> None:
    result = cli_runner("version")
    assert result.returncode == 0
    assert result.stdout.strip() == __version__


def test_gui_smoke_succeeds_offscreen(cli_runner) -> None:
    result = cli_runner("gui")
    assert result.returncode == 0
