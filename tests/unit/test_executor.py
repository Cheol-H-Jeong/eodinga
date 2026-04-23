from __future__ import annotations

import sqlite3
import unicodedata
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from eodinga.query import executor as executor_module
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
    local_now = datetime.now().astimezone()
    today_start = int(local_now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    yesterday_start = today_start - 86_400
    this_week_start = today_start - local_now.weekday() * 86_400
    last_month = int((local_now - timedelta(days=40)).timestamp())

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
    last_week_hits = [hit.file.name for hit in search(tmp_db, "date:last-week", limit=10).hits]
    assert "today.txt" not in last_week_hits
    last_month_hits = [hit.file.name for hit in search(tmp_db, "date:last-month", limit=10).hits]
    assert "old.txt" in last_month_hits


def test_execute_previous_period_date_queries_use_local_boundaries(
    tmp_db: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    seoul = ZoneInfo("Asia/Seoul")
    frozen_now = datetime(2026, 4, 23, 0, 30, tzinfo=seoul)
    last_week_hit = int(datetime(2026, 4, 13, 12, 0, tzinfo=seoul).timestamp())
    this_week_hit = int(datetime(2026, 4, 20, 12, 0, tzinfo=seoul).timestamp())
    last_month_hit = int(datetime(2026, 3, 15, 12, 0, tzinfo=seoul).timestamp())
    this_month_hit = int(datetime(2026, 4, 10, 12, 0, tzinfo=seoul).timestamp())

    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            if tz is None:
                return frozen_now.replace(tzinfo=None)
            return frozen_now.astimezone(tz)

    monkeypatch.setattr("eodinga.query.date_range.datetime", _FrozenDateTime)

    _insert_file(
        tmp_db,
        1,
        "/workspace/last-week.txt",
        512,
        last_week_hit,
        "txt",
        body_text="last week note",
    )
    _insert_file(
        tmp_db,
        2,
        "/workspace/this-week.txt",
        512,
        this_week_hit,
        "txt",
        body_text="this week note",
    )
    _insert_file(
        tmp_db,
        3,
        "/workspace/last-month.txt",
        512,
        last_month_hit,
        "txt",
        body_text="last month note",
    )
    _insert_file(
        tmp_db,
        4,
        "/workspace/this-month.txt",
        512,
        this_month_hit,
        "txt",
        body_text="this month note",
    )
    tmp_db.commit()

    last_week_hits = [hit.file.name for hit in search(tmp_db, "date:last-week", limit=10).hits]
    last_month_hits = [hit.file.name for hit in search(tmp_db, "date:last-month", limit=10).hits]

    assert last_week_hits == ["last-week.txt"]
    assert last_month_hits == ["last-month.txt"]


def test_execute_negated_case_true_restores_case_insensitive_matching(
    tmp_db: sqlite3.Connection,
) -> None:
    now = 1_713_528_000
    _insert_file(tmp_db, 1, "/workspace/Report.txt", 512, now, "txt", body_text="mixed case")
    tmp_db.commit()

    assert search(tmp_db, "case:true report", limit=5).hits == []
    hits = [hit.file.name for hit in search(tmp_db, "-case:true report", limit=5).hits]

    assert hits == ["Report.txt"]


def test_execute_negated_regex_true_restores_literal_term_matching(
    tmp_db: sqlite3.Connection,
) -> None:
    now = 1_713_528_000
    _insert_file(tmp_db, 1, "/workspace/report-7.txt", 512, now, "txt", body_text="regex candidate")
    _insert_file(tmp_db, 2, "/workspace/report-[0-9]+.txt", 512, now - 60, "txt", body_text="literal token")
    tmp_db.commit()

    regex_hits = [hit.file.name for hit in search(tmp_db, "regex:true report-[0-9]+", limit=5).hits]
    literal_hits = [hit.file.name for hit in search(tmp_db, "-regex:true report-[0-9]+", limit=5).hits]

    assert "report-7.txt" in regex_hits
    assert literal_hits == ["report-[0-9]+.txt"]


def test_execute_escaped_phrase_query_matches_literal_quotes_and_backslashes(
    tmp_db: sqlite3.Connection,
) -> None:
    _insert_file(
        tmp_db,
        1,
        r'/workspace/release "candidate" notes.txt',
        512,
        1_713_528_000,
        "txt",
        body_text='path C:\\workspace\\notes and release "candidate" sign-off',
    )
    tmp_db.commit()

    name_hits = [
        hit.file.name
        for hit in search(tmp_db, r'"release \"candidate\""', limit=5).hits
    ]
    content_hits = [
        hit.file.name
        for hit in search(tmp_db, r'content:"C:\\workspace\\notes"', limit=5).hits
    ]

    assert name_hits == ['release "candidate" notes.txt']
    assert content_hits == ['release "candidate" notes.txt']


def test_execute_phrase_query_matches_across_newlines_in_content(
    tmp_db: sqlite3.Connection,
) -> None:
    _insert_file(
        tmp_db,
        1,
        "/workspace/launch-plan.txt",
        512,
        1_713_528_000,
        "txt",
        body_text="launch\nchecklist and sign-off",
    )
    tmp_db.commit()

    hits = [hit.file.name for hit in search(tmp_db, 'content:"launch checklist"', limit=5).hits]

    assert hits == ["launch-plan.txt"]


def test_execute_phrase_query_matches_across_punctuation_in_path_and_content(
    tmp_db: sqlite3.Connection,
) -> None:
    _insert_file(
        tmp_db,
        1,
        "/workspace/launch-checklist.txt",
        512,
        1_713_528_000,
        "txt",
        body_text="launch/checklist approved",
    )
    tmp_db.commit()

    path_hits = [hit.file.name for hit in search(tmp_db, '"launch checklist"', limit=5).hits]
    content_hits = [hit.file.name for hit in search(tmp_db, 'content:"launch checklist"', limit=5).hits]

    assert path_hits == ["launch-checklist.txt"]
    assert content_hits == ["launch-checklist.txt"]


def test_execute_phrase_query_matches_across_underscores_in_path_and_content(
    tmp_db: sqlite3.Connection,
) -> None:
    _insert_file(
        tmp_db,
        1,
        "/workspace/launch_checklist.txt",
        512,
        1_713_528_000,
        "txt",
        body_text="launch_checklist approved",
    )
    tmp_db.commit()

    path_hits = [hit.file.name for hit in search(tmp_db, '"launch checklist"', limit=5).hits]
    content_hits = [hit.file.name for hit in search(tmp_db, 'content:"launch checklist"', limit=5).hits]

    assert path_hits == ["launch_checklist.txt"]
    assert content_hits == ["launch_checklist.txt"]


def test_execute_decomposed_korean_phrase_query_matches_across_punctuation(
    tmp_db: sqlite3.Connection,
) -> None:
    _insert_file(
        tmp_db,
        1,
        "/workspace/korean/회의록-초안.txt",
        512,
        1_713_528_000,
        "txt",
        body_text=unicodedata.normalize("NFD", "회의록-초안 정리본"),
    )
    tmp_db.commit()

    hits = [
        hit.file.name
        for hit in search(tmp_db, 'content:"회의록 초안"', limit=5).hits
    ]

    assert hits == ["회의록-초안.txt"]


def test_execute_relative_date_queries_use_local_day_boundaries(
    tmp_db: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    seoul = ZoneInfo("Asia/Seoul")
    frozen_now = datetime(2026, 4, 23, 0, 30, tzinfo=seoul)
    just_after_local_midnight = int(datetime(2026, 4, 23, 0, 5, tzinfo=seoul).timestamp())
    just_before_local_midnight = int(datetime(2026, 4, 22, 23, 55, tzinfo=seoul).timestamp())

    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            if tz is None:
                return frozen_now.replace(tzinfo=None)
            return frozen_now.astimezone(tz)

    monkeypatch.setattr("eodinga.query.date_range.datetime", _FrozenDateTime)

    _insert_file(
        tmp_db,
        1,
        "/workspace/local-today.txt",
        512,
        just_after_local_midnight,
        "txt",
        body_text="today note",
    )
    _insert_file(
        tmp_db,
        2,
        "/workspace/local-yesterday.txt",
        512,
        just_before_local_midnight,
        "txt",
        body_text="yesterday note",
    )
    tmp_db.commit()

    today_hits = [
        hit.file.name
        for hit in search(
            tmp_db,
            "date:today",
            limit=10,
        ).hits
    ]
    yesterday_hits = [hit.file.name for hit in search(tmp_db, "date:yesterday", limit=10).hits]

    assert today_hits == ["local-today.txt"]
    assert yesterday_hits == ["local-yesterday.txt"]


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


def test_execute_open_ended_date_ranges(tmp_db: sqlite3.Connection) -> None:
    jan_1 = int(datetime(2026, 1, 1, 12, tzinfo=UTC).timestamp())
    jan_2 = int(datetime(2026, 1, 2, 12, tzinfo=UTC).timestamp())
    jan_3 = int(datetime(2026, 1, 3, 12, tzinfo=UTC).timestamp())

    _insert_file(tmp_db, 1, "/workspace/jan-1.txt", 512, jan_1, "txt", body_text="jan 1")
    _insert_file(tmp_db, 2, "/workspace/jan-2.txt", 512, jan_2, "txt", body_text="jan 2")
    _insert_file(tmp_db, 3, "/workspace/jan-3.txt", 512, jan_3, "txt", body_text="jan 3")
    tmp_db.commit()

    newer_hits = [hit.file.name for hit in search(tmp_db, "date:2026-01-02..", limit=10).hits]
    older_hits = [hit.file.name for hit in search(tmp_db, "date:..2026-01-02", limit=10).hits]

    assert newer_hits == ["jan-2.txt", "jan-3.txt"]
    assert older_hits == ["jan-1.txt", "jan-2.txt"]


def test_execute_datetime_literal_and_range_queries(tmp_db: sqlite3.Connection) -> None:
    base = int(datetime(2026, 1, 3, 9, 15, 30, tzinfo=UTC).timestamp())
    _insert_file(tmp_db, 1, "/workspace/exact-second.txt", 512, base, "txt", body_text="exact")
    _insert_file(tmp_db, 2, "/workspace/later-second.txt", 512, base + 30, "txt", body_text="later")
    _insert_file(tmp_db, 3, "/workspace/day-neighbor.txt", 512, base + 300, "txt", body_text="neighbor")
    tmp_db.commit()

    exact_hits = [
        hit.file.name for hit in search(tmp_db, "modified:2026-01-03T09:15:30+00:00", limit=10).hits
    ]
    range_hits = [
        hit.file.name
        for hit in search(
            tmp_db,
            "modified:2026-01-03T09:15:30+00:00..2026-01-03T09:16:00+00:00",
            limit=10,
        ).hits
    ]

    assert exact_hits == ["exact-second.txt"]
    assert range_hits == ["exact-second.txt", "later-second.txt"]


def test_execute_datetime_query_accepts_lowercase_utc_suffix(tmp_db: sqlite3.Connection) -> None:
    base = int(datetime(2026, 1, 3, 9, 15, 30, tzinfo=UTC).timestamp())
    _insert_file(tmp_db, 1, "/workspace/exact-second.txt", 512, base, "txt", body_text="exact")
    tmp_db.commit()

    hits = [hit.file.name for hit in search(tmp_db, "modified:2026-01-03T09:15:30z", limit=10).hits]

    assert hits == ["exact-second.txt"]


def test_execute_decomposed_korean_path_filter_matches_nfc_paths(
    tmp_db: sqlite3.Connection,
) -> None:
    path = "/workspace/korean/회의록-봄.txt"
    _insert_file(tmp_db, 1, path, 512, 1_713_528_000, "txt", body_text="회의록 본문")
    tmp_db.commit()

    decomposed = unicodedata.normalize("NFD", "회의록")
    hits = [hit.file.name for hit in search(tmp_db, f"path:{decomposed}", limit=5).hits]

    assert hits == ["회의록-봄.txt"]


def test_execute_reuses_cached_sql_shapes_for_name_queries(populated_db: sqlite3.Connection) -> None:
    executor_module._path_candidates_fts_sql.cache_clear()
    executor_module._path_candidates_scan_sql.cache_clear()
    executor_module._record_batch_sql.cache_clear()

    first = search(populated_db, "doc-001", limit=5)
    second = search(populated_db, "doc-002", limit=5)

    assert first.hits
    assert second.hits
    assert executor_module._path_candidates_fts_sql.cache_info().hits >= 1


def test_execute_reuses_cached_sql_shapes_for_content_queries(
    populated_db: sqlite3.Connection,
) -> None:
    executor_module._content_candidates_sql.cache_clear()
    executor_module._auto_content_candidates_sql.cache_clear()
    executor_module._content_backfill_sql.cache_clear()

    first = search(populated_db, "content:launch", limit=5)
    second = search(populated_db, 'content:"alpha project 20"', limit=5)

    assert first.hits
    assert second.hits
    assert executor_module._content_candidates_sql.cache_info().hits >= 1


def test_execute_path_filter_with_short_unix_basename_literal(tmp_db: sqlite3.Connection) -> None:
    now = 1_713_528_000
    _insert_file(tmp_db, 1, "/tmp/log", 512, now, "", body_text="system log")
    _insert_file(tmp_db, 2, "/tmp/lag", 512, now - 60, "", body_text="other log")
    tmp_db.commit()

    hits = [hit.file.path.as_posix() for hit in search(tmp_db, "path:/tmp/log", limit=5).hits]

    assert hits == ["/tmp/log"]


def test_execute_path_filter_with_regex_like_short_unix_basename_literal(
    tmp_db: sqlite3.Connection,
) -> None:
    now = 1_713_528_000
    _insert_file(tmp_db, 1, "/tmp/ms", 512, now, "", body_text="literal path")
    _insert_file(tmp_db, 2, "/tmp/notes", 512, now - 60, "", body_text="other path")
    tmp_db.commit()

    hits = [hit.file.path.as_posix() for hit in search(tmp_db, "path:/tmp/ms", limit=5).hits]

    assert hits == ["/tmp/ms"]


def test_execute_path_filter_with_escaped_slash_regex(tmp_db: sqlite3.Connection) -> None:
    now = 1_713_528_000
    _insert_file(tmp_db, 1, "/tmp/logs/app.log", 512, now, "log", body_text="app")
    _insert_file(tmp_db, 2, "/tmp/notes/app.log", 512, now - 60, "log", body_text="notes")
    tmp_db.commit()

    hits = [hit.file.path.as_posix() for hit in search(tmp_db, r"path:/tmp\/logs/i", limit=5).hits]

    assert hits == ["/tmp/logs/app.log"]


def test_execute_inline_phrase_path_filter_decodes_backslashes(tmp_db: sqlite3.Connection) -> None:
    now = 1_713_528_000
    _insert_file(
        tmp_db,
        1,
        r"C:\workspace\notes\alpha.txt",
        512,
        now,
        "txt",
        body_text="windows path",
    )
    _insert_file(
        tmp_db,
        2,
        r"C:\workspace\archive\beta.txt",
        512,
        now - 60,
        "txt",
        body_text="archive path",
    )
    tmp_db.commit()

    hits = [str(hit.file.path) for hit in search(tmp_db, r'path:"C:\\workspace\\notes"', limit=5).hits]

    assert hits == [r"C:\workspace\notes\alpha.txt"]


def test_execute_unicode_python_path_scan_breaks_equal_name_ties_stably(
    tmp_db: sqlite3.Connection,
) -> None:
    now = 1_713_528_000
    _insert_file(tmp_db, 1, "/workspace/회의록/alpha/report.txt", 512, now, "txt")
    _insert_file(tmp_db, 2, "/workspace/회의록/beta/report.txt", 512, now, "txt")
    _insert_file(tmp_db, 3, "/workspace/회의록/gamma/report.txt", 512, now, "txt")
    tmp_db.commit()

    hits = search(tmp_db, "회의록 report", limit=10).hits

    assert [hit.file.id for hit in hits] == [1, 2, 3]


def test_execute_decomposed_korean_content_query_keeps_snippets(
    tmp_db: sqlite3.Connection,
) -> None:
    path = "/workspace/korean/회의록-봄.txt"
    _insert_file(tmp_db, 1, path, 512, 1_713_528_000, "txt", body_text="회의록 본문과 정리")
    tmp_db.commit()

    decomposed = unicodedata.normalize("NFD", "회의록")
    result = search(tmp_db, f"content:{decomposed}", limit=5)

    assert result.hits[0].file.name == "회의록-봄.txt"
    assert result.hits[0].snippet is not None
    assert "회의록" in result.hits[0].snippet


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


def test_execute_is_empty_queries(tmp_db: sqlite3.Connection) -> None:
    now = 1_713_528_000
    _insert_file(tmp_db, 1, "/workspace/empty-file.txt", 0, now, "txt", body_text="")
    _insert_file(tmp_db, 2, "/workspace/full-file.txt", 1, now - 60, "txt", body_text="x")
    _insert_file(tmp_db, 3, "/workspace/empty-dir", 0, now - 120, "", is_dir=True)
    _insert_file(tmp_db, 4, "/workspace/non-empty-dir", 0, now - 180, "", is_dir=True)
    _insert_file(tmp_db, 5, "/workspace/non-empty-dir/note.txt", 1, now - 240, "txt", body_text="child")
    tmp_db.commit()

    empty_hits = [hit.file.path.as_posix() for hit in search(tmp_db, "is:empty", limit=10).hits]
    non_empty_hits = [hit.file.path.as_posix() for hit in search(tmp_db, "-is:empty", limit=10).hits]

    assert empty_hits == ["/workspace/empty-dir", "/workspace/empty-file.txt"]
    assert "/workspace/non-empty-dir" in non_empty_hits
    assert "/workspace/full-file.txt" in non_empty_hits
    assert "/workspace/non-empty-dir/note.txt" in non_empty_hits


def test_execute_size_range_queries(tmp_db: sqlite3.Connection) -> None:
    now = 1_713_528_000
    _insert_file(tmp_db, 1, "/workspace/tiny.txt", 99, now, "txt", body_text="tiny")
    _insert_file(tmp_db, 2, "/workspace/in-range-low.txt", 100, now - 60, "txt", body_text="low")
    _insert_file(
        tmp_db,
        3,
        "/workspace/in-range-high.txt",
        500 * 1024,
        now - 120,
        "txt",
        body_text="high",
    )
    _insert_file(tmp_db, 4, "/workspace/too-large.txt", 500 * 1024 + 1, now - 180, "txt", body_text="large")
    tmp_db.commit()

    hits = [hit.file.name for hit in search(tmp_db, "size:100..500K", limit=10).hits]
    reversed_hits = [hit.file.name for hit in search(tmp_db, "size:500K..100", limit=10).hits]
    negated_hits = [hit.file.name for hit in search(tmp_db, "-size:100..500K", limit=10).hits]

    assert hits == ["in-range-high.txt", "in-range-low.txt"]
    assert reversed_hits == hits
    assert negated_hits == ["tiny.txt", "too-large.txt"]


def test_execute_metadata_only_query_reports_uncapped_total_estimate(
    tmp_db: sqlite3.Connection,
) -> None:
    now = 1_713_528_000
    total_files = 1_205
    for index in range(1, total_files + 1):
        _insert_file(
            tmp_db,
            index,
            f"/workspace/archive-{index:04d}.txt",
            2_048,
            now - index,
            "txt",
        )
    tmp_db.commit()

    result = search(tmp_db, "size:>1K", limit=5)

    assert [hit.file.name for hit in result.hits] == [
        "archive-0001.txt",
        "archive-0002.txt",
        "archive-0003.txt",
        "archive-0004.txt",
        "archive-0005.txt",
    ]
    assert result.total_estimate == total_files


def test_execute_metadata_only_or_query_reports_union_total_estimate(
    tmp_db: sqlite3.Connection,
) -> None:
    now = 1_713_528_000
    for index in range(1, 901):
        _insert_file(
            tmp_db,
            index,
            f"/workspace/dupe-{index:04d}.txt",
            12 * 1024 * 1024,
            now - index,
            "txt",
            content_hash=b"shared-dupe",
        )
    for index in range(901, 1_251):
        _insert_file(
            tmp_db,
            index,
            f"/workspace/large-{index:04d}.txt",
            12 * 1024 * 1024,
            now - index,
            "txt",
            content_hash=f"unique-{index}".encode(),
        )
    for index in range(1_251, 1_401):
        _insert_file(
            tmp_db,
            index,
            f"/workspace/small-{index:04d}.txt",
            512,
            now - index,
            "txt",
            content_hash=f"small-{index}".encode(),
        )
    tmp_db.commit()

    result = search(tmp_db, "is:duplicate | size:>10M", limit=3)

    assert [hit.file.name for hit in result.hits] == [
        "dupe-0001.txt",
        "dupe-0002.txt",
        "dupe-0003.txt",
    ]
    assert result.total_estimate == 1_250


def test_execute_regex_true_query(tmp_db: sqlite3.Connection) -> None:
    now = 1_713_528_000
    _insert_file(tmp_db, 1, "/workspace/report-011.py", 1024, now, "py", body_text="launch")
    _insert_file(tmp_db, 2, "/workspace/notes.txt", 1024, now - 60, "txt", body_text="misc")
    tmp_db.commit()

    hits = [hit.file.name for hit in search(tmp_db, "regex:true report-[0-9]+", limit=10).hits]

    assert hits == ["report-011.py"]


def test_execute_regex_only_query_scans_beyond_initial_window(tmp_db: sqlite3.Connection) -> None:
    now = 1_713_528_000
    for index in range(1, 1501):
        name = f"alpha-{index:04d}.txt"
        if index == 1500:
            name = "needle-1500.txt"
        _insert_file(
            tmp_db,
            index,
            f"/workspace/{name}",
            1024,
            now - index,
            "txt",
            body_text="bulk",
        )
    tmp_db.commit()

    hits = [hit.file.name for hit in search(tmp_db, "/needle-[0-9]+/", limit=10).hits]

    assert hits == ["needle-1500.txt"]


def test_execute_negated_group_query(tmp_db: sqlite3.Connection) -> None:
    now = 1_713_528_000
    _insert_file(tmp_db, 1, "/workspace/alpha-plan.txt", 1024, now, "txt", body_text="alpha")
    _insert_file(tmp_db, 2, "/workspace/beta-plan.txt", 1024, now - 60, "txt", body_text="beta")
    _insert_file(tmp_db, 3, "/workspace/gamma-plan.txt", 1024, now - 120, "txt", body_text="gamma")
    _insert_file(tmp_db, 4, "/workspace/notes.md", 1024, now - 180, "md", body_text="misc")
    tmp_db.commit()

    hits = [hit.file.name for hit in search(tmp_db, "-(alpha | beta) ext:txt", limit=10).hits]
    assert hits == ["gamma-plan.txt"]


def test_execute_negated_group_query_applies_demorgan_truth_table(
    tmp_db: sqlite3.Connection,
) -> None:
    now = 1_713_528_000
    _insert_file(tmp_db, 1, "/workspace/alpha-only.txt", 1024, now, "txt", body_text="alpha")
    _insert_file(
        tmp_db,
        2,
        "/workspace/beta-gamma.txt",
        1024,
        now - 60,
        "txt",
        body_text="beta gamma",
    )
    _insert_file(tmp_db, 3, "/workspace/beta-only.txt", 1024, now - 120, "txt", body_text="beta")
    _insert_file(tmp_db, 4, "/workspace/gamma-only.txt", 1024, now - 180, "txt", body_text="gamma")
    _insert_file(tmp_db, 5, "/workspace/neutral.txt", 1024, now - 240, "txt", body_text="neutral")
    tmp_db.commit()

    hits = [hit.file.name for hit in search(tmp_db, "-(alpha | beta gamma) ext:txt", limit=10).hits]

    assert hits == ["beta-only.txt", "gamma-only.txt", "neutral.txt"]


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


def test_execute_korean_filename_query_matches_decomposed_hangul(tmp_db: sqlite3.Connection) -> None:
    now = 1_713_528_000
    decomposed = unicodedata.normalize("NFD", "프로젝트-회의록.txt")
    _insert_file(tmp_db, 1, f"/workspace/문서함/{decomposed}", 1024, now, "txt", body_text="meeting")
    _insert_file(tmp_db, 2, "/workspace/문서함/프로젝트보고서.txt", 1024, now - 60, "txt", body_text="report")
    tmp_db.commit()

    hits = [hit.file.name for hit in search(tmp_db, "회의록", limit=10).hits]
    assert hits == [decomposed]


def test_execute_korean_path_filter_matches_decomposed_hangul(tmp_db: sqlite3.Connection) -> None:
    now = 1_713_528_000
    decomposed = unicodedata.normalize("NFD", "프로젝트-회의록.txt")
    _insert_file(tmp_db, 1, f"/workspace/문서함/{decomposed}", 1024, now, "txt", body_text="meeting")
    _insert_file(tmp_db, 2, "/workspace/문서함/프로젝트보고서.txt", 1024, now - 60, "txt", body_text="report")
    tmp_db.commit()

    hits = [hit.file.name for hit in search(tmp_db, "path:회의록", limit=10).hits]
    assert hits == [decomposed]


def test_execute_negated_korean_path_filter_matches_normalized_path_text(
    tmp_db: sqlite3.Connection,
) -> None:
    now = 1_713_528_000
    decomposed = unicodedata.normalize("NFD", "프로젝트-회의록.txt")
    _insert_file(tmp_db, 1, f"/workspace/문서함/{decomposed}", 1024, now, "txt", body_text="meeting")
    _insert_file(tmp_db, 2, "/workspace/문서함/프로젝트보고서.txt", 1024, now - 60, "txt", body_text="report")
    _insert_file(tmp_db, 3, "/workspace/문서함/영수증.txt", 1024, now - 120, "txt", body_text="receipt")
    tmp_db.commit()

    hits = [hit.file.name for hit in search(tmp_db, "-path:회의록 ext:txt", limit=10).hits]
    assert hits == ["영수증.txt", "프로젝트보고서.txt"]


def test_execute_korean_content_query_supplements_partial_fts_hits(tmp_db: sqlite3.Connection) -> None:
    now = 1_713_528_000
    decomposed = unicodedata.normalize("NFD", "회의록 본문")
    _insert_file(tmp_db, 1, "/workspace/문서함/meeting-nfc.txt", 1024, now, "txt", body_text="회의록 본문")
    _insert_file(tmp_db, 2, "/workspace/문서함/meeting-nfd.txt", 1024, now - 60, "txt", body_text=decomposed)
    _insert_file(tmp_db, 3, "/workspace/문서함/report.txt", 1024, now - 120, "txt", body_text="보고서 본문")
    tmp_db.commit()

    hits = [hit.file.name for hit in search(tmp_db, "content:회의록", limit=10).hits]
    assert hits == ["meeting-nfc.txt", "meeting-nfd.txt"]


def test_execute_plain_korean_query_supplements_partial_auto_content_hits(
    tmp_db: sqlite3.Connection,
) -> None:
    now = 1_713_528_000
    decomposed = unicodedata.normalize("NFD", "회의록 본문")
    _insert_file(tmp_db, 1, "/workspace/문서함/회의록-요약.txt", 1024, now, "txt", body_text="summary")
    _insert_file(tmp_db, 2, "/workspace/문서함/meeting-nfd.txt", 1024, now - 60, "txt", body_text=decomposed)
    _insert_file(tmp_db, 3, "/workspace/문서함/report.txt", 1024, now - 120, "txt", body_text="보고서 본문")
    tmp_db.commit()

    hits = [hit.file.name for hit in search(tmp_db, "회의록", limit=10).hits]
    assert hits == ["회의록-요약.txt", "meeting-nfd.txt"]


def test_execute_plain_negated_term_filters_auto_content_hits(tmp_db: sqlite3.Connection) -> None:
    now = 1_713_528_000
    _insert_file(tmp_db, 1, "/workspace/reports/alpha.txt", 1024, now, "txt", body_text="note launch")
    _insert_file(tmp_db, 2, "/workspace/reports/beta.txt", 1024, now - 60, "txt", body_text="note archive")
    _insert_file(tmp_db, 3, "/workspace/reports/gamma.txt", 1024, now - 120, "txt", body_text="archive only")
    tmp_db.commit()

    hits = [hit.file.name for hit in search(tmp_db, "note -launch", limit=10).hits]
    assert hits == ["beta.txt"]


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


def test_plain_query_skips_content_fts_when_no_content_is_indexed(tmp_db: sqlite3.Connection) -> None:
    now = 1_713_528_000
    _insert_file(tmp_db, 1, "/workspace/projects/report-011.py", 1024, now, "py")
    _insert_file(tmp_db, 2, "/workspace/archive/report-011.txt", 1024, now - 60, "txt")
    tmp_db.commit()

    statements: list[str] = []
    tmp_db.set_trace_callback(statements.append)
    try:
        hits = [hit.file.name for hit in search(tmp_db, "report-011", limit=10).hits]
    finally:
        tmp_db.set_trace_callback(None)

    assert hits == ["report-011.py", "report-011.txt"]
    assert not any("FROM content_fts" in statement for statement in statements)


def test_plain_query_caches_content_presence_probe_until_connection_changes(
    tmp_db: sqlite3.Connection,
) -> None:
    now = 1_713_528_000
    _insert_file(tmp_db, 1, "/workspace/projects/report-011.py", 1024, now, "py")
    tmp_db.commit()

    statements: list[str] = []
    tmp_db.set_trace_callback(statements.append)
    try:
        search(tmp_db, "report-011", limit=10)
        search(tmp_db, "report-011", limit=10)
    finally:
        tmp_db.set_trace_callback(None)

    assert sum("SELECT 1 FROM content_map LIMIT 1" in statement for statement in statements) == 1

    _insert_file(
        tmp_db,
        2,
        "/workspace/projects/report-012.py",
        1024,
        now - 60,
        "py",
        body_text="launch",
    )
    tmp_db.commit()

    statements = []
    tmp_db.set_trace_callback(statements.append)
    try:
        search(tmp_db, "report", limit=10)
    finally:
        tmp_db.set_trace_callback(None)

    assert sum("SELECT 1 FROM content_map LIMIT 1" in statement for statement in statements) == 1


def test_plain_ascii_query_skips_substring_scan_when_fts_already_hits(
    tmp_db: sqlite3.Connection,
) -> None:
    now = 1_713_528_000
    _insert_file(tmp_db, 1, "/workspace/projects/report-011.py", 1024, now, "py")
    _insert_file(tmp_db, 2, "/workspace/archive/report-011.txt", 1024, now - 60, "txt")
    tmp_db.commit()

    statements: list[str] = []
    tmp_db.set_trace_callback(statements.append)
    try:
        hits = [hit.file.name for hit in search(tmp_db, "report-011", limit=10).hits]
    finally:
        tmp_db.set_trace_callback(None)

    assert hits == ["report-011.py", "report-011.txt"]
    assert not any("instr(lower(files.name)" in statement for statement in statements)


def test_search_root_scope_matches_windows_style_paths(tmp_db: sqlite3.Connection) -> None:
    now = 1_713_528_000
    _insert_file(tmp_db, 1, r"C:\workspace\reports\alpha.txt", 1024, now, "txt", body_text="alpha")
    _insert_file(
        tmp_db,
        2,
        r"C:\workspace\archive\alpha.txt",
        1024,
        now - 60,
        "txt",
        body_text="alpha archive",
    )
    tmp_db.commit()

    hits = [
        hit.file.path
        for hit in search(tmp_db, "alpha", limit=10, root=Path("C:/workspace/reports")).hits
    ]

    assert hits == [Path(r"C:\workspace\reports\alpha.txt")]


def test_plain_query_can_fall_back_to_content_matches(tmp_db: sqlite3.Connection) -> None:
    now = 1_713_528_000
    _insert_file(tmp_db, 1, "/workspace/projects/alpha.txt", 1024, now, "txt", body_text="launch checklist")
    _insert_file(tmp_db, 2, "/workspace/projects/beta.txt", 1024, now - 60, "txt", body_text="meeting notes")
    tmp_db.commit()

    hits = [hit.file.name for hit in search(tmp_db, "launch", limit=10).hits]

    assert hits == ["alpha.txt"]


def test_execute_double_negated_group_query(tmp_db: sqlite3.Connection) -> None:
    now = 1_713_528_000
    _insert_file(tmp_db, 1, "/workspace/alpha.txt", 1024, now, "txt", body_text="alpha")
    _insert_file(tmp_db, 2, "/workspace/beta.txt", 1024, now - 60, "txt", body_text="beta")
    _insert_file(tmp_db, 3, "/workspace/gamma.txt", 1024, now - 120, "txt", body_text="gamma")
    tmp_db.commit()

    hits = [hit.file.name for hit in search(tmp_db, "-(-(alpha | beta))", limit=10).hits]
    assert hits == ["alpha.txt", "beta.txt"]
