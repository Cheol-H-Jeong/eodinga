from __future__ import annotations

import sys
import threading
from io import StringIO
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
    emit_crash_log,
    install_crash_hooks,
    reset_metrics,
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


def test_configure_logging_uses_rotating_utf8_file_sink(tmp_path: Path, monkeypatch) -> None:
    calls: list[tuple[object, dict[str, object]]] = []
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr("eodinga.observability.logger.remove", lambda: None)
    monkeypatch.setattr(
        "eodinga.observability.logger.add",
        lambda sink, **kwargs: calls.append((sink, kwargs)),
    )

    configure_logging("warning", log_path=tmp_path / "logs" / "app.log")

    assert len(calls) == 2
    stderr_sink, stderr_kwargs = calls[0]
    file_sink, file_kwargs = calls[1]
    assert stderr_sink is sys.stderr
    assert stderr_kwargs["diagnose"] is False
    assert stderr_kwargs["level"] == "WARNING"
    assert file_sink == tmp_path / "logs" / "app.log"
    assert file_kwargs["rotation"] == "5 MB"
    assert file_kwargs["retention"] == 5
    assert file_kwargs["encoding"] == "utf-8"
    assert file_kwargs["enqueue"] is True


def test_configure_logging_uses_env_override(tmp_path: Path, monkeypatch) -> None:
    log_path = tmp_path / "custom" / "override.log"
    monkeypatch.setenv("EODINGA_LOG_PATH", str(log_path))
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    configure_logging("INFO")
    assert log_path.parent.exists()


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


def test_emit_crash_log_reports_location_to_stderr(tmp_path: Path) -> None:
    stderr = StringIO()
    try:
        raise RuntimeError("boom")
    except RuntimeError as error:
        crash_path = emit_crash_log(error, context="emit", crash_dir=tmp_path, stderr=stderr)
    assert str(crash_path) in stderr.getvalue()


def test_install_crash_hooks_captures_thread_exception(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("EODINGA_CRASH_DIR", str(tmp_path))
    monkeypatch.setattr("eodinga.observability._CRASH_HOOKS_INSTALLED", False)
    stderr = StringIO()
    original_excepthook = sys.excepthook
    original_unraisablehook = sys.unraisablehook
    original_threading_hook = threading.excepthook
    install_crash_hooks(stderr=stderr)
    try:
        raise RuntimeError("thread boom")
    except RuntimeError as error:
        args = SimpleNamespace(
            exc_type=RuntimeError,
            exc_value=error,
            exc_traceback=error.__traceback__,
            thread=SimpleNamespace(name="watcher"),
        )
    try:
        cast(Any, threading.excepthook)(args)
        crash_logs = sorted(tmp_path.glob("crash-*.log"))
        assert len(crash_logs) == 1
        contents = crash_logs[0].read_text(encoding="utf-8")
        assert "Unhandled exception in thread watcher" in contents
        assert "thread=watcher" in contents
        assert "RuntimeError: thread boom" in contents
        assert str(crash_logs[0]) in stderr.getvalue()
    finally:
        sys.excepthook = original_excepthook
        sys.unraisablehook = original_unraisablehook
        threading.excepthook = original_threading_hook


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
