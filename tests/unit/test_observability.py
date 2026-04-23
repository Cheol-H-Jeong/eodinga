from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import cast

from eodinga.common import WatchEvent
from eodinga.content.base import ParserSpec
from eodinga.content.registry import parse
from eodinga.core.watcher import WatchService
from eodinga.observability import (
    counter_value,
    configure_logging,
    default_crash_dir,
    default_log_path,
    increment_counter,
    logger,
    reset_metrics,
    resolve_file_log_config,
    runtime_metadata,
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
    logger.info("hello file sink")
    logger.complete()
    assert log_path.parent.exists()
    assert "hello file sink" in log_path.read_text(encoding="utf-8")


def test_configure_logging_uses_env_override(tmp_path: Path, monkeypatch) -> None:
    log_path = tmp_path / "custom" / "override.log"
    monkeypatch.setenv("EODINGA_LOG_PATH", str(log_path))
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    configure_logging("INFO")
    assert log_path.parent.exists()


def test_resolve_file_log_config_supports_env_overrides(tmp_path: Path, monkeypatch) -> None:
    log_path = tmp_path / "logs" / "custom.log"
    monkeypatch.setenv("EODINGA_LOG_PATH", str(log_path))
    monkeypatch.setenv("EODINGA_LOG_ROTATION", "10 MB")
    monkeypatch.setenv("EODINGA_LOG_RETENTION", "7 days")
    monkeypatch.setenv("EODINGA_LOG_COMPRESSION", "gz")
    monkeypatch.setenv("EODINGA_LOG_SERIALIZE", "1")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    config = resolve_file_log_config()

    assert config is not None
    assert config.path == log_path
    assert config.rotation == "10 MB"
    assert config.retention == "7 days"
    assert config.compression == "gz"
    assert config.serialize is True


def test_write_crash_log_captures_traceback(tmp_path: Path) -> None:
    reset_metrics()
    increment_counter("queries_served")
    try:
        raise RuntimeError("boom")
    except RuntimeError as error:
        crash_path = write_crash_log(error, crash_dir=tmp_path, command="search boom")
    contents = crash_path.read_text(encoding="utf-8")
    assert crash_path.parent == tmp_path
    assert "RuntimeError: boom" in contents
    assert "Traceback" in contents
    assert "timestamp=" in contents
    assert "command=search boom" in contents
    assert "version=" in contents
    assert "platform=" in contents
    assert "python=" in contents
    assert "cwd=" in contents
    assert "pid=" in contents
    assert "metrics.counters=queries_served:1" in contents
    assert counter_value("crashes_written") == 1


def test_write_crash_log_uses_env_override(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("EODINGA_CRASH_DIR", str(tmp_path))
    try:
        raise ValueError("env boom")
    except ValueError as error:
        crash_path = write_crash_log(error, context="env override")
    assert crash_path.parent == tmp_path
    assert "env override" in crash_path.read_text(encoding="utf-8")


def test_runtime_metadata_reports_process_context() -> None:
    metadata = runtime_metadata()

    assert metadata["version"]
    assert metadata["platform"] == sys.platform
    assert metadata["python"]
    assert metadata["cwd"] == str(Path.cwd())
    assert metadata["pid"] == os.getpid()


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
