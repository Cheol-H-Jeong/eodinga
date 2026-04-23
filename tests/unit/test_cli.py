from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path, PureWindowsPath
from threading import Thread
from time import sleep

import pytest

from eodinga import __version__
from eodinga.__main__ import main
from eodinga.common import WatchEvent
from eodinga.content.base import ParserSpec
from eodinga.content.registry import parse
from eodinga.core.watcher import WatchService
from eodinga.index.schema import apply_schema
from eodinga.observability import reset_metrics, snapshot_metrics


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
        local_now = datetime.now().astimezone()
        today_start = int(
            local_now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
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


def test_search_json_reports_total_count_not_page_length(cli_runner, tmp_path: Path) -> None:
    db_path = tmp_path / "index.db"
    conn = sqlite3.connect(db_path)
    try:
        apply_schema(conn)
        for file_id in range(1, 1_206):
            _insert_file(
                conn,
                file_id,
                f"/workspace/bulk/doc-{file_id:04d}.txt",
                2_048,
                1_713_528_000 - file_id,
                "txt",
            )
        conn.commit()
    finally:
        conn.close()

    result = cli_runner(
        "--db",
        str(db_path),
        "search",
        "size:>1K",
        "--json",
        "--limit",
        "5",
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["count"] == 1_205
    assert payload["returned"] == 5
    assert len(payload["results"]) == 5


def test_search_json_executes_regex_mode_query(cli_runner, tmp_path: Path) -> None:
    db_path = tmp_path / "index.db"
    _build_search_db(db_path)

    result = cli_runner(
        "--db",
        str(db_path),
        "search",
        "regex:true today-alpha-.*",
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


def test_search_json_plain_negated_term_filters_auto_content_hits(cli_runner, tmp_path: Path) -> None:
    db_path = tmp_path / "index.db"
    _build_search_db(db_path)

    result = cli_runner(
        "--db",
        str(db_path),
        "search",
        "note -launch",
        "--json",
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert [Path(item["path"]).name for item in payload["results"]] == ["yesterday-beta.txt"]


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


def test_search_json_honors_windows_style_root_filter(cli_runner, tmp_path: Path) -> None:
    db_path = tmp_path / "index.db"
    conn = sqlite3.connect(db_path)
    try:
        apply_schema(conn)
        conn.execute(
            "INSERT INTO roots(id, path, include, exclude, added_at) VALUES (?, ?, ?, ?, ?)",
            (1, r"C:\workspace", "[]", "[]", 1),
        )
        for file_id, raw_path, mtime, body_text in (
            (1, r"C:\workspace\reports\alpha.txt", 1_713_528_000, "alpha inside scoped root"),
            (2, r"C:\workspace\archive\alpha.txt", 1_713_527_000, "alpha outside scoped root"),
        ):
            path_obj = PureWindowsPath(raw_path)
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
                    raw_path,
                    str(path_obj.parent),
                    path_obj.name,
                    path_obj.name.lower(),
                    "txt",
                    1024,
                    mtime,
                    mtime,
                    0,
                    0,
                    None,
                    mtime,
                ),
            )
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
        conn.commit()
    finally:
        conn.close()

    result = cli_runner(
        "--db",
        str(db_path),
        "search",
        "alpha",
        "--json",
        "--root",
        "C:/workspace/reports",
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert [item["path"] for item in payload["results"]] == [r"C:\workspace\reports\alpha.txt"]


def test_search_reports_invalid_query_cleanly(cli_runner, tmp_path: Path) -> None:
    db_path = tmp_path / "index.db"
    _build_search_db(db_path)

    result = cli_runner("--db", str(db_path), "search", "content:", "--json")

    assert result.returncode == 2
    assert "expected operator value" in result.stderr


@pytest.mark.parametrize(
    ("query", "expected_message"),
    [
        ("case:maybe duplicate", "invalid boolean value"),
        ("date:2026-01-01..bogus duplicate", "invalid date literal"),
        ("/[a-/", "invalid regex"),
        ("content:/todo/ii", "duplicate regex flag"),
    ],
)
def test_search_reports_invalid_semantic_query_cleanly(
    cli_runner, tmp_path: Path, query: str, expected_message: str
) -> None:
    db_path = tmp_path / "index.db"
    _build_search_db(db_path)

    result = cli_runner("--db", str(db_path), "search", query, "--json")

    assert result.returncode == 2
    assert expected_message in result.stderr


def test_search_accepts_is_aliases(cli_runner, tmp_path: Path) -> None:
    db_path = tmp_path / "index.db"
    _build_search_db(db_path)

    result = cli_runner("--db", str(db_path), "search", "is:FILE", "--json")

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["results"]


def test_version_matches_package(cli_runner) -> None:
    result = cli_runner("version")
    assert result.returncode == 0
    assert result.stdout.strip() == __version__


def test_gui_smoke_succeeds_offscreen(cli_runner) -> None:
    result = cli_runner("gui")
    assert result.returncode == 0


def test_index_json_rebuilds_searchable_database(cli_runner, tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    docs = tmp_path / "docs"
    reports.mkdir()
    docs.mkdir()
    (reports / "launch-plan.txt").write_text("launcher recovery checklist\n", encoding="utf-8")
    (docs / "notes.md").write_text("secondary workspace note\n", encoding="utf-8")
    db_path = tmp_path / "index.db"

    result = cli_runner(
        "--db",
        str(db_path),
        "index",
        "--root",
        str(reports),
        "--root",
        str(docs),
        "--rebuild",
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["command"] == "index"
    assert payload["db"] == str(db_path)
    assert payload["roots"] == [str(reports), str(docs)]
    assert payload["files_indexed"] >= 2
    assert not db_path.with_name(".index.db.next").exists()

    search_result = cli_runner(
        "--db",
        str(db_path),
        "search",
        "launcher",
        "--json",
    )

    assert search_result.returncode == 0
    search_payload = json.loads(search_result.stdout)
    assert [Path(item["path"]).name for item in search_payload["results"]] == ["launch-plan.txt"]


def test_index_requires_at_least_one_root(cli_runner, tmp_path: Path) -> None:
    db_path = tmp_path / "index.db"

    result = cli_runner("--db", str(db_path), "index", "--rebuild")

    assert result.returncode == 2
    assert "requires at least one root" in result.stderr


def test_stats_json_emits_runtime_counters(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "index.db"
    _build_search_db(db_path)
    reset_metrics()

    search_exit = main(["--db", str(db_path), "search", "duplicate", "--json"])
    search_output = capsys.readouterr()
    assert search_exit == 0
    assert json.loads(search_output.out)["count"] == 2

    stats_exit = main(["--db", str(db_path), "stats", "--json"])
    stats_output = capsys.readouterr()
    assert stats_exit == 0
    payload = json.loads(stats_output.out)
    generated_at = datetime.fromisoformat(payload["generated_at"].replace("Z", "+00:00"))
    assert generated_at.tzinfo is not None
    assert payload["uptime_ms"] >= 0
    assert payload["files_indexed"] == 3
    assert payload["documents_indexed"] == 3
    assert payload["queries_served"] == 1
    assert payload["queries_zero_results"] == 0
    assert payload["queries_truncated"] == 0
    assert payload["parser_errors"] == 0
    assert payload["watcher_events"] == 0
    assert payload["watcher_flushes"] == 0
    assert payload["watcher_events_flushed"] == 0
    assert payload["watcher_queue_full"] == 0
    assert payload["watcher_enqueue_aborted"] == 0
    assert payload["index_rebuilds_completed"] == 0
    assert payload["commands_started"] == 2
    assert payload["commands_completed"] == 1
    assert payload["commands_failed"] == 0
    assert payload["crashes_reported"] == 0
    assert payload["crash_logs_written"] == 0
    assert payload["logging_configurations"] == 2
    assert payload["log_sinks_stderr_configured"] == 2
    assert payload["log_sinks_file_configured"] == 0
    assert payload["log_sinks_file_disabled"] == 2
    assert payload["query_latency_histogram"]["count"] == 1
    assert payload["query_result_count_histogram"]["count"] == 1
    assert payload["command_latency_histogram"]["count"] == 1
    assert payload["watch_flush_batch_histogram"] == {}
    assert payload["watch_event_lag_histogram"] == {}
    assert payload["watcher_queue_backpressure_histogram"] == {}
    assert payload["index_rebuild_latency_histogram"] == {}
    assert payload["index_batch_size_histogram"] == {}
    assert payload["commands"]["search"]["completed"] == 1
    assert payload["commands"]["search"]["started"] == 1
    assert payload["commands"]["stats"]["started"] == 1
    assert payload["exit_codes"]["0"] == 1
    assert payload["file_logging_enabled"] is True
    assert payload["log_path"] is None
    assert payload["log_rotation"] == "5 MB"
    assert payload["log_retention"] == 5
    assert payload["log_compression"] is None
    assert payload["crash_dir"]
    assert payload["counters"]["queries_served"] == 1
    assert payload["counters"]["commands_started"] == 2
    assert payload["counters"]["logging_configurations"] == 2
    assert payload["counters"]["log_sinks.stderr.configured"] == 2
    assert payload["counters"]["log_sinks.file.disabled"] == 2
    assert payload["counters"]["commands.search.completed"] == 1
    assert payload["counters"]["commands.stats.started"] == 1
    assert payload["histograms"]["query_latency_ms"]["count"] == 1
    assert payload["histograms"]["query_result_count"]["count"] == 1
    assert payload["histograms"]["command_latency_ms"]["count"] == 1


def test_stats_json_exposes_end_to_end_runtime_metrics(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "alpha.txt").write_text("alpha launch note\n", encoding="utf-8")
    (docs / "beta.txt").write_text("beta launch note\n", encoding="utf-8")
    broken = tmp_path / "broken.txt"
    broken.write_text("broken parser input\n", encoding="utf-8")
    db_path = tmp_path / "index.db"
    reset_metrics()

    index_exit = main(["--db", str(db_path), "index", "--root", str(docs), "--rebuild"])
    index_output = capsys.readouterr()
    assert index_exit == 0
    indexed_files = json.loads(index_output.out)["files_indexed"]
    assert indexed_files >= 2

    spec = ParserSpec(
        name="broken",
        parse=lambda _path, _max_chars: (_ for _ in ()).throw(ValueError("parse failed")),
        extensions=frozenset({"txt"}),
        max_bytes=1024,
    )
    monkeypatch.setattr("eodinga.content.registry.get_spec_for", lambda _path: spec)
    parse(broken, max_body_chars=128)

    service = WatchService(queue_maxsize=1)
    service.record(
        WatchEvent(
            event_type="created",
            path=docs / "gamma.txt",
            root_path=docs,
            happened_at=1.0,
        )
    )
    service._flush_ready(force=True)
    blocked = Thread(
        target=lambda: (
            service.record(
                WatchEvent(
                    event_type="modified",
                    path=docs / "gamma.txt",
                    root_path=docs,
                    happened_at=2.0,
                )
            ),
            service._flush_ready(force=True),
        ),
        daemon=True,
    )
    blocked.start()
    sleep(0.1)
    first_event = service.queue.get_nowait()
    assert first_event.path == docs / "gamma.txt"
    blocked.join(timeout=1)
    assert not blocked.is_alive()
    second_event = service.queue.get_nowait()
    assert second_event.path == docs / "gamma.txt"

    search_exit = main(["--db", str(db_path), "search", "launch", "--json", "--limit", "1"])
    search_output = capsys.readouterr()
    assert search_exit == 0
    assert json.loads(search_output.out)["count"] == 2

    stats_exit = main(["--db", str(db_path), "stats", "--json"])
    stats_output = capsys.readouterr()
    assert stats_exit == 0
    payload = json.loads(stats_output.out)
    assert payload["counters"]["files_indexed"] == indexed_files
    assert payload["counters"]["parser_errors"] == 1
    assert payload["counters"]["parsers.broken.error"] == 1
    assert payload["counters"]["queries_served"] == 1
    assert "queries_zero_results" not in payload["counters"]
    assert payload["counters"]["queries_truncated"] == 1
    assert payload["counters"]["watcher_events"] == 2
    assert payload["counters"]["watcher_flushes"] == 2
    assert payload["counters"]["watcher_events_flushed"] == 2
    assert payload["counters"]["watcher_queue_full"] == 1
    assert "watcher_enqueue_aborted" not in payload["counters"]
    assert payload["watcher_events"] == 2
    assert payload["watcher_flushes"] == 2
    assert payload["watcher_events_flushed"] == 2
    assert payload["watcher_queue_full"] == 1
    assert payload["watcher_enqueue_aborted"] == 0
    assert payload["process_started_at"].endswith("Z")
    assert payload["pid"] > 0
    assert payload["version"] == __version__
    assert payload["counters"]["logging_configurations"] == 3
    assert payload["counters"]["log_sinks.stderr.configured"] == 3
    assert payload["counters"]["log_sinks.file.disabled"] == 3
    assert payload["logging_configurations"] == 3
    assert payload["log_sinks_stderr_configured"] == 3
    assert payload["log_sinks_file_configured"] == 0
    assert payload["log_sinks_file_disabled"] == 3
    assert payload["commands_started"] == 3
    assert payload["commands_completed"] == 2
    assert payload["commands_failed"] == 0
    assert payload["crashes_reported"] == 0
    assert payload["crash_logs_written"] == 0
    assert payload["crash_handlers_installed"] == 3
    assert payload["index_rebuilds_completed"] == 1
    assert payload["queries_zero_results"] == 0
    assert payload["queries_truncated"] == 1
    assert payload["commands"]["index"]["completed"] == 1
    assert payload["commands"]["search"]["completed"] == 1
    assert payload["commands"]["stats"]["started"] == 1
    assert payload["exit_codes"]["0"] == 2
    assert payload["log_rotation"] == "5 MB"
    assert payload["log_retention"] == 5
    assert payload["log_compression"] is None
    assert payload["histograms"]["query_latency_ms"]["count"] == 1
    assert payload["histograms"]["query_result_count"]["count"] == 1
    assert payload["histograms"]["command_latency_ms"]["count"] == 2
    assert payload["query_result_count_histogram"]["count"] == 1
    assert payload["watch_flush_batch_histogram"]["count"] == 2
    assert payload["watch_event_lag_histogram"]["count"] == 2
    assert payload["watcher_queue_backpressure_histogram"]["count"] == 1
    assert payload["index_rebuild_latency_histogram"]["count"] == 1
    assert payload["index_batch_size_histogram"]["count"] >= 1


def test_stats_json_exposes_zero_result_query_metrics(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "index.db"
    _build_search_db(db_path)
    reset_metrics()

    search_exit = main(["--db", str(db_path), "search", "missing-term", "--json"])
    search_output = capsys.readouterr()
    assert search_exit == 0
    assert json.loads(search_output.out)["count"] == 0

    stats_exit = main(["--db", str(db_path), "stats", "--json"])
    stats_output = capsys.readouterr()
    assert stats_exit == 0
    payload = json.loads(stats_output.out)
    assert payload["queries_served"] == 1
    assert payload["queries_zero_results"] == 1
    assert payload["queries_truncated"] == 0
    assert payload["query_result_count_histogram"]["count"] == 1
    assert payload["query_result_count_histogram"]["min_ms"] == 0.0
    assert payload["counters"]["queries_zero_results"] == 1
    assert "queries_truncated" not in payload["counters"]


def test_failed_command_increments_command_failure_metrics(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "index.db"
    _build_search_db(db_path)
    reset_metrics()

    def _boom(_args) -> int:
        raise RuntimeError("version exploded")

    monkeypatch.setattr("eodinga.__main__._cmd_version", _boom)

    exit_code = main(["--db", str(db_path), "version"])

    metrics = snapshot_metrics()
    assert exit_code == 1
    assert metrics["counters"]["commands_started"] == 1
    assert metrics["counters"]["commands.version.started"] == 1
    assert metrics["counters"]["commands_failed"] == 1
    assert metrics["counters"]["commands.version.failed"] == 1
    assert metrics["counters"]["crashes_reported"] == 1
    assert metrics["counters"]["crash_logs_written"] == 1
    assert "commands_completed" not in metrics["counters"]
    assert metrics["histograms"]["command_latency_ms"]["count"] == 1


def test_interrupted_command_returns_130_without_crash_metrics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "index.db"
    _build_search_db(db_path)
    reset_metrics()

    def _interrupt(_args) -> int:
        raise KeyboardInterrupt

    monkeypatch.setattr("eodinga.__main__._cmd_version", _interrupt)

    exit_code = main(["--db", str(db_path), "version"])

    metrics = snapshot_metrics()
    assert exit_code == 130
    assert metrics["counters"]["commands_started"] == 1
    assert metrics["counters"]["commands.version.started"] == 1
    assert metrics["counters"]["commands_interrupted"] == 1
    assert metrics["counters"]["commands.version.interrupted"] == 1
    assert "commands_failed" not in metrics["counters"]
    assert "crashes_reported" not in metrics["counters"]
    assert metrics["counters"]["commands.exit_code.130"] == 1
    assert metrics["histograms"]["command_latency_ms"]["count"] == 1


def test_nonzero_command_exit_counts_as_failed_without_crash_metrics(
    tmp_path: Path, capsys
) -> None:
    db_path = tmp_path / "index.db"
    _build_search_db(db_path)
    reset_metrics()

    exit_code = main(["--db", str(db_path), "search", "date:invalid", "--json"])

    captured = capsys.readouterr()
    metrics = snapshot_metrics()
    assert exit_code == 2
    assert "invalid date" in captured.err
    assert metrics["counters"]["commands_started"] == 1
    assert metrics["counters"]["commands.search.started"] == 1
    assert metrics["counters"]["commands_failed"] == 1
    assert metrics["counters"]["commands.search.failed"] == 1
    assert "commands_completed" not in metrics["counters"]
    assert "crashes_reported" not in metrics["counters"]
    assert metrics["counters"]["commands.exit_code.2"] == 1
    assert metrics["histograms"]["command_latency_ms"]["count"] == 1


def test_stats_json_structures_failed_command_and_exit_code_counts(tmp_path: Path, capsys, monkeypatch) -> None:
    db_path = tmp_path / "index.db"
    _build_search_db(db_path)
    reset_metrics()

    def _boom(_args) -> int:
        raise RuntimeError("search exploded")

    monkeypatch.setattr("eodinga.__main__._cmd_version", _boom)

    exit_code = main(["--db", str(db_path), "version"])
    assert exit_code == 1
    capsys.readouterr()

    stats_exit = main(["--db", str(db_path), "stats", "--json"])
    stats_output = capsys.readouterr()
    assert stats_exit == 0
    payload = json.loads(stats_output.out)
    assert payload["commands"]["version"]["failed"] == 1
    assert payload["commands"]["version"]["started"] == 1
    assert payload["exit_codes"]["1"] == 1


def test_stats_json_structures_interrupted_command_counts(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "index.db"
    _build_search_db(db_path)
    reset_metrics()

    def _interrupt(_args) -> int:
        raise KeyboardInterrupt

    monkeypatch.setattr("eodinga.__main__._cmd_version", _interrupt)

    exit_code = main(["--db", str(db_path), "version"])
    assert exit_code == 130
    capsys.readouterr()

    stats_exit = main(["--db", str(db_path), "stats", "--json"])
    stats_output = capsys.readouterr()
    assert stats_exit == 0
    payload = json.loads(stats_output.out)
    assert payload["commands_interrupted"] == 1
    assert payload["commands"]["version"]["interrupted"] == 1
    assert payload["commands"]["version"]["started"] == 1
    assert payload["exit_codes"]["130"] == 1


def test_stats_json_structures_nonzero_exit_failures(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "index.db"
    _build_search_db(db_path)
    reset_metrics()

    exit_code = main(["--db", str(db_path), "search", "date:invalid", "--json"])
    assert exit_code == 2
    capsys.readouterr()

    stats_exit = main(["--db", str(db_path), "stats", "--json"])
    stats_output = capsys.readouterr()
    assert stats_exit == 0
    payload = json.loads(stats_output.out)
    assert payload["commands_failed"] == 1
    assert payload["commands"]["search"]["failed"] == 1
    assert payload["commands"]["search"]["started"] == 1
    assert payload["exit_codes"]["2"] == 1
