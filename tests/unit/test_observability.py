from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import cast

from loguru import logger

from eodinga.common import WatchEvent
from eodinga.content.base import ParserSpec
from eodinga.content.registry import parse
from eodinga.core.watcher import WatchService
from eodinga.observability import (
    configure_logging,
    default_crash_dir,
    default_log_path,
    get_logger,
    observability_runtime,
    reset_metrics,
    resolve_log_path,
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


def test_configure_logging_writes_component_rich_records(tmp_path: Path) -> None:
    log_path = tmp_path / "logs" / "app.log"
    configure_logging("INFO", log_path=log_path)

    get_logger("unit-test").info("hello observability")
    logger.complete()

    contents = log_path.read_text(encoding="utf-8")
    assert "INFO" in contents
    assert "unit-test" in contents
    assert "hello observability" in contents


def test_configure_logging_uses_env_override(tmp_path: Path, monkeypatch) -> None:
    log_path = tmp_path / "custom" / "override.log"
    monkeypatch.setenv("EODINGA_LOG_PATH", str(log_path))
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    configure_logging("INFO")
    assert log_path.parent.exists()


def test_resolve_log_path_respects_disable_and_pytest(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EODINGA_DISABLE_FILE_LOGGING", "1")
    assert resolve_log_path() is None

    monkeypatch.delenv("EODINGA_DISABLE_FILE_LOGGING", raising=False)
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tests/unit/test_observability.py::test")
    monkeypatch.delenv("EODINGA_LOG_PATH", raising=False)
    assert resolve_log_path() is None

    explicit = tmp_path / "logs" / "explicit.log"
    assert resolve_log_path(explicit) == explicit


def test_observability_runtime_uses_overrides(tmp_path: Path, monkeypatch) -> None:
    log_path = tmp_path / "runtime" / "app.log"
    crash_dir = tmp_path / "crashes"
    monkeypatch.setenv("EODINGA_LOG_PATH", str(log_path))
    monkeypatch.setenv("EODINGA_CRASH_DIR", str(crash_dir))
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    runtime = observability_runtime()

    assert runtime["file_logging_enabled"] is True
    assert runtime["log_path"] == log_path
    assert runtime["crash_dir"] == crash_dir
    assert str(runtime["timestamp_utc"]).endswith("Z")


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
    assert "platform=" in contents


def test_write_crash_log_uses_env_override(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("EODINGA_CRASH_DIR", str(tmp_path))
    try:
        raise ValueError("env boom")
    except ValueError as error:
        crash_path = write_crash_log(error, context="env override")
    assert crash_path.parent == tmp_path
    assert "env override" in crash_path.read_text(encoding="utf-8")


def test_write_crash_log_avoids_timestamp_collisions(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("eodinga.observability.current_timestamp", lambda: "20260423T120000Z")

    first = write_crash_log(RuntimeError("first"), crash_dir=tmp_path)
    second = write_crash_log(RuntimeError("second"), crash_dir=tmp_path)

    assert first.name == "crash-20260423T120000Z.log"
    assert second.name == f"crash-20260423T120000Z-{os.getpid()}.log"
    assert "RuntimeError: second" in second.read_text(encoding="utf-8")


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
    assert counters["watcher_events.created"] == 1


def test_watcher_event_type_counters_track_multiple_event_kinds() -> None:
    service = WatchService()
    reset_metrics()

    service.record(WatchEvent(event_type="created", path=Path("/tmp/report.txt")))
    service.record(WatchEvent(event_type="modified", path=Path("/tmp/report.txt")))
    service.record(WatchEvent(event_type="deleted", path=Path("/tmp/report.txt")))

    counters = cast(dict[str, int], snapshot_metrics()["counters"])
    assert counters["watcher_events"] == 3
    assert counters["watcher_events.created"] == 1
    assert counters["watcher_events.modified"] == 1
    assert counters["watcher_events.deleted"] == 1
