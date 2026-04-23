from __future__ import annotations

import sys
from pathlib import Path
from threading import Thread
from time import sleep
from typing import cast

from eodinga.common import WatchEvent
from eodinga.content.base import ParserSpec
from eodinga.content.registry import parse
from eodinga.core.watcher import WatchService
from eodinga import __version__
from eodinga.observability import (
    configure_logging,
    default_crash_dir,
    default_log_path,
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


def test_watcher_queue_backpressure_counter_increments(tmp_path: Path) -> None:
    service = WatchService(queue_maxsize=1)
    reset_metrics()
    first = WatchEvent(
        event_type="created",
        path=tmp_path / "first.txt",
        root_path=tmp_path,
        happened_at=1.0,
    )
    second = WatchEvent(
        event_type="modified",
        path=tmp_path / "second.txt",
        root_path=tmp_path,
        happened_at=2.0,
    )
    service.queue.put(first)
    service.record(second)

    thread = Thread(target=lambda: service._flush_ready(force=True), daemon=True)
    thread.start()
    sleep(0.1)

    counters = cast(dict[str, int], snapshot_metrics()["counters"])
    assert counters["watcher_queue_backpressure"] == 1

    assert service.queue.get_nowait() == first
    thread.join(timeout=1)
    assert service.queue.get_nowait() == second
