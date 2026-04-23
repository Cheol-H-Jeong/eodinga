from __future__ import annotations

import io
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from eodinga.common import WatchEvent
from eodinga.content.base import ParserSpec, empty_content
from eodinga.content.registry import parse
from eodinga.core.watcher import WatchService
from eodinga import __version__
from eodinga.observability import (
    configure_logging,
    default_crash_dir,
    default_log_path,
    file_logging_enabled,
    increment_counter,
    install_crash_handlers,
    recent_snapshots,
    record_histogram,
    record_snapshot,
    resolve_crash_dir,
    resolve_log_compression,
    resolve_log_path,
    resolve_log_retention,
    resolve_log_rotation,
    reset_metrics,
    report_crash,
    snapshot_metrics,
    write_crash_log,
)


def test_default_log_and_crash_paths_follow_platform_state_dirs(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_STATE_HOME", "/tmp/eodinga-state")
    assert default_log_path() == Path("/tmp/eodinga-state/eodinga/logs/eodinga.log")
    assert default_crash_dir() == Path("/tmp/eodinga-state/eodinga/crashes")

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\tester\AppData\Local")
    assert default_log_path() == Path(r"C:\Users\tester\AppData\Local/eodinga/logs/eodinga.log")

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    assert default_log_path() == Path.home() / "Library" / "Logs" / "eodinga" / "eodinga.log"
    assert default_crash_dir() == Path.home() / "Library" / "Logs" / "eodinga" / "crashes"


def test_configure_logging_respects_explicit_file_target(tmp_path: Path) -> None:
    log_path = tmp_path / "logs" / "app.log"
    reset_metrics()
    configure_logging("DEBUG", log_path=log_path)
    counters = cast(dict[str, int], snapshot_metrics()["counters"])
    assert log_path.parent.exists()
    assert counters["logging_configurations"] == 1
    assert counters["log_sinks.stderr.configured"] == 1
    assert counters["log_sinks.file.configured"] == 1


def test_install_crash_handlers_records_installation_metric() -> None:
    reset_metrics()

    install_crash_handlers()

    counters = cast(dict[str, int], snapshot_metrics()["counters"])
    assert counters["crash_handlers_installed"] == 1


def test_configure_logging_uses_env_override(tmp_path: Path, monkeypatch) -> None:
    log_path = tmp_path / "custom" / "override.log"
    monkeypatch.setenv("EODINGA_LOG_PATH", str(log_path))
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    reset_metrics()
    configure_logging("INFO")
    counters = cast(dict[str, int], snapshot_metrics()["counters"])
    assert log_path.parent.exists()
    assert counters["log_sinks.file.configured"] == 1


def test_log_and_crash_resolution_respect_runtime_overrides(tmp_path: Path, monkeypatch) -> None:
    log_path = tmp_path / "logs" / "custom.log"
    crash_dir = tmp_path / "crashes"
    monkeypatch.setenv("EODINGA_LOG_PATH", str(log_path))
    monkeypatch.setenv("EODINGA_CRASH_DIR", str(crash_dir))
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    assert resolve_log_path() == log_path
    assert resolve_crash_dir() == crash_dir
    assert file_logging_enabled() is True


def test_log_policy_resolution_respects_runtime_overrides(monkeypatch) -> None:
    monkeypatch.setenv("EODINGA_LOG_ROTATION", "12 MB")
    monkeypatch.setenv("EODINGA_LOG_RETENTION", "7")
    monkeypatch.setenv("EODINGA_LOG_COMPRESSION", "zip")

    assert resolve_log_rotation() == "12 MB"
    assert resolve_log_retention() == 7
    assert resolve_log_compression() == "zip"


def test_log_resolution_returns_none_when_file_logging_disabled(monkeypatch) -> None:
    monkeypatch.setenv("EODINGA_DISABLE_FILE_LOGGING", "1")
    reset_metrics()

    assert file_logging_enabled() is False
    assert resolve_log_path() is None
    configure_logging("INFO")
    counters = cast(dict[str, int], snapshot_metrics()["counters"])
    assert counters["logging_configurations"] == 1
    assert counters["log_sinks.stderr.configured"] == 1
    assert counters["log_sinks.file.disabled"] == 1
    assert "log_sinks.file.configured" not in counters


def test_write_crash_log_captures_traceback(tmp_path: Path) -> None:
    try:
        raise RuntimeError("boom")
    except RuntimeError as error:
        crash_path = write_crash_log(error, crash_dir=tmp_path, details={"argv": ["search", "boom"]})
    contents = crash_path.read_text(encoding="utf-8")
    assert crash_path.parent == tmp_path
    assert "RuntimeError: boom" in contents
    assert "Traceback" in contents
    assert "timestamp=" in contents
    assert "process_started_at=" in contents
    assert "uptime_ms=" in contents
    assert "pid=" in contents
    assert "thread_count=" in contents
    assert "rss_bytes=" in contents
    assert "open_fd_count=" in contents
    assert f"version={__version__}" in contents
    assert f"platform={sys.platform}" in contents
    assert f"thread={threading.current_thread().name}" in contents
    assert f"executable={sys.executable}" in contents
    assert f"cwd={Path.cwd()}" in contents
    assert f"crash_dir={tmp_path}" in contents
    assert "file_logging_enabled=True" in contents
    assert 'argv=["search", "boom"]' in contents


def test_write_crash_log_uses_env_override(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("EODINGA_CRASH_DIR", str(tmp_path))
    try:
        raise ValueError("env boom")
    except ValueError as error:
        crash_path = write_crash_log(error, context="env override")
    assert crash_path.parent == tmp_path
    assert "env override" in crash_path.read_text(encoding="utf-8")


def test_write_crash_log_records_resolved_log_state(tmp_path: Path, monkeypatch) -> None:
    log_path = tmp_path / "logs" / "eodinga.log"
    monkeypatch.setenv("EODINGA_LOG_PATH", str(log_path))
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    try:
        raise RuntimeError("log state")
    except RuntimeError as error:
        crash_path = write_crash_log(error, crash_dir=tmp_path)

    contents = crash_path.read_text(encoding="utf-8")
    assert f"log_path={log_path}" in contents
    assert "log_rotation=5 MB" in contents
    assert "log_retention=5" in contents
    assert "log_compression=None" in contents


def test_write_crash_log_records_runtime_metrics(tmp_path: Path) -> None:
    reset_metrics()
    increment_counter("queries_served", 2)
    record_histogram("query_latency_ms", 12.5)
    record_snapshot("command.search", {"query": "metrics boom", "count": 2})

    try:
        raise RuntimeError("metrics boom")
    except RuntimeError as error:
        crash_path = write_crash_log(error, crash_dir=tmp_path)

    contents = crash_path.read_text(encoding="utf-8")
    assert '"queries_served": 2' in contents
    assert '"snapshots_recorded": 1' in contents
    assert '"query_latency_ms"' in contents
    assert "metrics_generated_at=" in contents
    assert 'recent_snapshots=[{"name": "command.search"' in contents


def test_write_crash_log_uses_unique_path_when_timestamp_collides(tmp_path: Path) -> None:
    try:
        raise RuntimeError("first")
    except RuntimeError as first:
        first_path = write_crash_log(first, crash_dir=tmp_path)

    try:
        raise RuntimeError("second")
    except RuntimeError as second:
        second_path = write_crash_log(second, crash_dir=tmp_path)

    assert first_path != second_path
    assert first_path.exists()
    assert second_path.exists()


def test_report_crash_writes_log_and_stderr(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("EODINGA_CRASH_DIR", str(tmp_path))
    reset_metrics()

    crash_path = report_crash(RuntimeError("boom"), context="reported crash")

    captured = capsys.readouterr()
    assert crash_path is not None
    assert str(crash_path) in captured.err
    assert "reported crash" in crash_path.read_text(encoding="utf-8")
    counters = cast(dict[str, int], snapshot_metrics()["counters"])
    assert counters["crashes.RuntimeError"] == 1


def test_report_crash_records_write_failure_without_raising(monkeypatch, capsys) -> None:
    reset_metrics()

    def _fail_write(*_args: object, **_kwargs: object) -> Path:
        raise OSError("disk full")

    monkeypatch.setattr("eodinga.observability.write_crash_log", _fail_write)

    crash_path = report_crash(RuntimeError("boom"), context="reported crash")

    captured = capsys.readouterr()
    counters = cast(dict[str, int], snapshot_metrics()["counters"])
    assert crash_path is None
    assert "failed to write crash log" in captured.err
    assert "disk full" in captured.err
    assert counters["crashes.RuntimeError"] == 1
    assert counters["crashes_reported"] == 1
    assert counters["crash_log_write_failures"] == 1
    assert "crash_logs_written" not in counters


def test_install_crash_handlers_writes_thread_crash_log(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("EODINGA_CRASH_DIR", str(tmp_path))
    install_crash_handlers()

    try:
        raise RuntimeError("thread boom")
    except RuntimeError as error:
        args = cast(
            Any,
            SimpleNamespace(
                exc_type=type(error),
                exc_value=error,
                exc_traceback=error.__traceback__,
                thread=threading.current_thread(),
            ),
        )
    threading.excepthook(args)

    captured = capsys.readouterr()
    crash_logs = sorted(tmp_path.glob("crash-*.log"))
    assert len(crash_logs) == 1
    assert str(crash_logs[0]) in captured.err
    contents = crash_logs[0].read_text(encoding="utf-8")
    assert "Unhandled thread exception" in contents
    assert f"thread={threading.current_thread().name}" in contents


def test_install_crash_handlers_writes_unraisable_crash_log(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("EODINGA_CRASH_DIR", str(tmp_path))
    stderr = io.StringIO()
    install_crash_handlers(stream=stderr)

    try:
        raise RuntimeError("unraisable boom")
    except RuntimeError as error:
        args = cast(
            Any,
            SimpleNamespace(
                exc_type=type(error),
                exc_value=error,
                exc_traceback=error.__traceback__,
                err_msg="while finalizing",
                object=SimpleNamespace(name="cleanup"),
            ),
        )
    sys.unraisablehook(args)

    crash_logs = sorted(tmp_path.glob("crash-*.log"))
    assert len(crash_logs) == 1
    assert str(crash_logs[0]) in stderr.getvalue()
    contents = crash_logs[0].read_text(encoding="utf-8")
    assert "Unhandled unraisable exception" in contents
    assert "err_msg=while finalizing" in contents
    assert "RuntimeError: unraisable boom" in contents


def test_parser_error_counter_increments_for_failed_parse(monkeypatch, tmp_path: Path) -> None:
    broken = tmp_path / "broken.txt"
    broken.write_text("bad", encoding="utf-8")
    spec = ParserSpec(
        name="broken",
        parse=lambda _path, _max_chars: (_ for _ in ()).throw(ValueError("parse failed")),
        extensions=frozenset({"txt"}),
        max_bytes=1024,
    )
    reset_metrics()
    monkeypatch.setattr("eodinga.content.registry.get_spec_for", lambda _path: spec)

    parse(broken, max_body_chars=128)

    counters = cast(dict[str, int], snapshot_metrics()["counters"])
    assert counters["parser_errors"] == 1
    assert counters["parsers.broken.error"] == 1


def test_parser_success_counter_increments_for_successful_parse(monkeypatch, tmp_path: Path) -> None:
    document = tmp_path / "ok.txt"
    document.write_text("hello parser", encoding="utf-8")
    spec = ParserSpec(
        name="ok",
        parse=lambda path, _max_chars: empty_content(path),
        extensions=frozenset({"txt"}),
        max_bytes=1024,
    )
    reset_metrics()
    monkeypatch.setattr("eodinga.content.registry.get_spec_for", lambda _path: spec)

    parse(document, max_body_chars=128)

    counters = cast(dict[str, int], snapshot_metrics()["counters"])
    assert counters["parsers.ok.parsed"] == 1


def test_parser_skipped_too_large_counter_increments(monkeypatch, tmp_path: Path) -> None:
    document = tmp_path / "large.txt"
    document.write_text("x" * 32, encoding="utf-8")
    spec = ParserSpec(
        name="tiny-limit",
        parse=lambda path, _max_chars: empty_content(path),
        extensions=frozenset({"txt"}),
        max_bytes=4,
    )
    reset_metrics()
    monkeypatch.setattr("eodinga.content.registry.get_spec_for", lambda _path: spec)

    parse(document, max_body_chars=128)

    counters = cast(dict[str, int], snapshot_metrics()["counters"])
    assert counters["parsers.tiny-limit.skipped_too_large"] == 1


def test_watcher_event_counter_increments() -> None:
    service = WatchService()
    reset_metrics()

    service.record(WatchEvent(event_type="created", path=Path("/tmp/report.txt")))

    counters = cast(dict[str, int], snapshot_metrics()["counters"])
    assert counters["watcher_events"] == 1
    assert counters["watcher_events.created"] == 1


def test_watcher_flush_metrics_increment(tmp_path: Path) -> None:
    service = WatchService()
    reset_metrics()

    service.record(
        WatchEvent(
            event_type="modified",
            path=tmp_path / "report.txt",
            root_path=tmp_path,
            happened_at=1.0,
        )
    )
    service._flush_ready(force=True)

    metrics = snapshot_metrics()
    counters = cast(dict[str, int], metrics["counters"])
    histograms = cast(dict[str, dict[str, object]], metrics["histograms"])
    assert counters["watcher_flushes"] == 1
    assert counters["watcher_events_flushed"] == 1
    assert histograms["watch_flush_batch_size"]["count"] == 1
    assert histograms["watch_event_lag_ms"]["count"] == 1


def test_watcher_backpressure_metrics_increment(tmp_path: Path) -> None:
    from threading import Thread
    from time import sleep

    service = WatchService(queue_maxsize=1)
    reset_metrics()

    service.record(
        WatchEvent(
            event_type="created",
            path=tmp_path / "first.txt",
            root_path=tmp_path,
            happened_at=1.0,
        )
    )
    service._flush_ready(force=True)

    thread = Thread(
        target=lambda: (
            service.record(
                WatchEvent(
                    event_type="created",
                    path=tmp_path / "second.txt",
                    root_path=tmp_path,
                    happened_at=2.0,
                )
            ),
            service._flush_ready(force=True),
        ),
        daemon=True,
    )
    thread.start()
    sleep(0.1)
    service.queue.get_nowait()
    thread.join(timeout=1)
    service.queue.get_nowait()

    metrics = snapshot_metrics()
    counters = cast(dict[str, int], metrics["counters"])
    histograms = cast(dict[str, dict[str, object]], metrics["histograms"])
    assert counters["watcher_queue_full"] == 1
    assert histograms["watcher_queue_backpressure_ms"]["count"] == 1


def test_snapshot_metrics_exposes_runtime_generation_metadata() -> None:
    reset_metrics()

    metrics = snapshot_metrics()

    assert metrics["generated_at"].endswith("Z")
    assert metrics["process_started_at"].endswith("Z")
    assert metrics["pid"] > 0
    assert metrics["thread_count"] >= 1
    assert metrics["rss_bytes"] is None or metrics["rss_bytes"] > 0
    assert metrics["open_fd_count"] is None or metrics["open_fd_count"] >= 0
    assert metrics["version"] == __version__
    assert metrics["uptime_ms"] >= 0


def test_record_snapshot_keeps_recent_entries_bounded() -> None:
    reset_metrics()

    for index in range(25):
        record_snapshot("command.search", {"index": index})

    snapshots = recent_snapshots()
    assert len(snapshots) == 20
    assert snapshots[0]["payload"]["index"] == 5
    assert snapshots[-1]["payload"]["index"] == 24
    metrics = snapshot_metrics()
    counters = cast(dict[str, int], metrics["counters"])
    assert counters["snapshots_recorded"] == 25
    assert counters["snapshots_dropped"] == 5
