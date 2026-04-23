from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import cast

from eodinga.common import WatchEvent
from eodinga.content.base import ParserSpec
from eodinga.content.registry import parse
from eodinga.core.watcher import WatchService
from eodinga.observability import (
    configure_logging,
    default_crash_dir,
    default_log_path,
    install_crash_handler,
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
    monkeypatch.setenv("HOME", "/Users/tester")
    assert default_log_path() == Path("/Users/tester/Library/Logs/eodinga/eodinga.log")
    assert default_crash_dir() == Path("/Users/tester/Library/Application Support/eodinga/crashes")


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


def test_write_crash_log_captures_traceback(tmp_path: Path) -> None:
    try:
        raise RuntimeError("boom")
    except RuntimeError as error:
        crash_path = write_crash_log(error, crash_dir=tmp_path)
    contents = crash_path.read_text(encoding="utf-8")
    assert crash_path.parent == tmp_path
    assert "RuntimeError: boom" in contents
    assert "Traceback" in contents
    assert "timestamp=" in contents
    assert "pid=" in contents


def test_write_crash_log_uses_env_override(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("EODINGA_CRASH_DIR", str(tmp_path))
    try:
        raise ValueError("env boom")
    except ValueError as error:
        crash_path = write_crash_log(error, context="env override")
    assert crash_path.parent == tmp_path
    assert "env override" in crash_path.read_text(encoding="utf-8")


def test_install_crash_handler_writes_uncaught_main_exception(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("EODINGA_CRASH_DIR", str(tmp_path))
    install_crash_handler("stats --json")

    try:
        raise RuntimeError("hook boom")
    except RuntimeError as error:
        sys.excepthook(type(error), error, error.__traceback__)

    output = capsys.readouterr().err
    crash_logs = sorted(tmp_path.glob("crash-*.log"))
    assert "crash log written to" in output
    assert len(crash_logs) == 1
    assert "Unhandled exception while running: stats --json" in crash_logs[0].read_text(
        encoding="utf-8"
    )


def test_install_crash_handler_writes_uncaught_thread_exception(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("EODINGA_CRASH_DIR", str(tmp_path))
    install_crash_handler("gui")

    try:
        raise ValueError("thread boom")
    except ValueError as error:
        args = threading.ExceptHookArgs(
            (type(error), error, error.__traceback__, threading.current_thread())
        )
        threading.excepthook(args)

    output = capsys.readouterr().err
    crash_logs = sorted(tmp_path.glob("crash-*.log"))
    assert "crash log written to" in output
    assert len(crash_logs) == 1
    assert "[thread=MainThread]" in crash_logs[0].read_text(encoding="utf-8")


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
