from __future__ import annotations

import io
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from eodinga.common import WatchEvent
from eodinga.content.base import ParserSpec
from eodinga.content.registry import parse
from eodinga.core.watcher import WatchService
from eodinga import __version__
from eodinga.observability import (
    configure_logging,
    default_crash_dir,
    default_log_path,
    file_logging_enabled,
    install_crash_handlers,
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
    configure_logging("DEBUG", log_path=log_path)
    assert log_path.parent.exists()


def test_configure_logging_uses_env_override(tmp_path: Path, monkeypatch) -> None:
    log_path = tmp_path / "custom" / "override.log"
    monkeypatch.setenv("EODINGA_LOG_PATH", str(log_path))
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    configure_logging("INFO")
    assert log_path.parent.exists()


def test_log_and_crash_resolution_respect_runtime_overrides(tmp_path: Path, monkeypatch) -> None:
    log_path = tmp_path / "logs" / "custom.log"
    crash_dir = tmp_path / "crashes"
    monkeypatch.setenv("EODINGA_LOG_PATH", str(log_path))
    monkeypatch.setenv("EODINGA_CRASH_DIR", str(crash_dir))
    monkeypatch.setenv("EODINGA_LOG_ROTATION", "12 MB")
    monkeypatch.setenv("EODINGA_LOG_RETENTION", "9")
    monkeypatch.setenv("EODINGA_LOG_COMPRESSION", "gz")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    assert resolve_log_path() == log_path
    assert resolve_log_rotation() == "12 MB"
    assert resolve_log_retention() == 9
    assert resolve_log_compression() == "gz"
    assert resolve_crash_dir() == crash_dir
    assert file_logging_enabled() is True


def test_log_resolution_returns_none_when_file_logging_disabled(monkeypatch) -> None:
    monkeypatch.setenv("EODINGA_DISABLE_FILE_LOGGING", "1")

    assert file_logging_enabled() is False
    assert resolve_log_path() is None


def test_log_settings_fall_back_to_defaults(monkeypatch) -> None:
    monkeypatch.delenv("EODINGA_LOG_ROTATION", raising=False)
    monkeypatch.delenv("EODINGA_LOG_RETENTION", raising=False)
    monkeypatch.delenv("EODINGA_LOG_COMPRESSION", raising=False)

    assert resolve_log_rotation() == "5 MB"
    assert resolve_log_retention() == 5
    assert resolve_log_compression() is None


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
    assert "pid=" in contents
    assert f"version={__version__}" in contents
    assert f"platform={sys.platform}" in contents
    assert f"cwd={Path.cwd()}" in contents
    assert 'argv=["search", "boom"]' in contents


def test_write_crash_log_uses_env_override(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("EODINGA_CRASH_DIR", str(tmp_path))
    try:
        raise ValueError("env boom")
    except ValueError as error:
        crash_path = write_crash_log(error, context="env override")
    assert crash_path.parent == tmp_path
    assert "env override" in crash_path.read_text(encoding="utf-8")


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

    crash_path = report_crash(RuntimeError("boom"), context="reported crash")

    captured = capsys.readouterr()
    assert str(crash_path) in captured.err
    assert "reported crash" in crash_path.read_text(encoding="utf-8")


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


def test_watcher_event_counter_increments() -> None:
    service = WatchService()
    reset_metrics()

    service.record(WatchEvent(event_type="created", path=Path("/tmp/report.txt")))

    counters = cast(dict[str, int], snapshot_metrics()["counters"])
    assert counters["watcher_events"] == 1


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
    assert metrics["uptime_ms"] >= 0
