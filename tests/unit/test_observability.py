from __future__ import annotations

import sys
from pathlib import Path
from typing import cast

import eodinga.content.registry as registry
from eodinga.common import WatchEvent
from eodinga.config import RootConfig
from eodinga.content.base import ParserSpec
from eodinga.content.registry import parse
from eodinga.core.watcher import WatchService
from eodinga.index.build import rebuild_index
from eodinga.index.storage import open_index
from eodinga.observability import (
    configure_logging,
    default_crash_dir,
    default_log_path,
    reset_metrics,
    snapshot_metrics,
    write_crash_log,
)
from eodinga.query import search


def test_default_log_and_crash_paths_follow_platform_state_dirs(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_STATE_HOME", "/tmp/eodinga-state")
    assert default_log_path() == Path("/tmp/eodinga-state/eodinga/logs/eodinga.log")
    assert default_crash_dir() == Path("/tmp/eodinga-state/eodinga/crashes")

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\tester\AppData\Local")
    assert default_log_path() == Path(r"C:\Users\tester\AppData\Local/eodinga/logs/eodinga.log")

    monkeypatch.setattr(sys, "platform", "darwin")
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
        crash_path = write_crash_log(error, crash_dir=tmp_path)
    contents = crash_path.read_text(encoding="utf-8")
    assert crash_path.parent == tmp_path
    assert "RuntimeError: boom" in contents
    assert "Traceback" in contents
    assert "timestamp=" in contents
    assert "pid=" in contents
    assert "platform=" in contents
    assert "python=" in contents
    assert "cwd=" in contents
    assert "argv=" in contents


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


def test_metrics_increment_end_to_end_across_runtime_flows(
    monkeypatch, tmp_path: Path
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "report.txt").write_text("alpha report body", encoding="utf-8")
    broken = root / "broken.boom"
    broken.write_text("bad", encoding="utf-8")
    db_path = tmp_path / "index.db"
    broken_spec = ParserSpec(
        name="broken",
        parse=lambda _path, _max_chars: (_ for _ in ()).throw(ValueError("parse failed")),
        extensions=frozenset({"boom"}),
        max_bytes=1024,
    )
    original_get_spec_for = registry.get_spec_for

    def patched_get_spec_for(path: Path) -> ParserSpec | None:
        if path.suffix == ".boom":
            return broken_spec
        return original_get_spec_for(path)

    reset_metrics()
    monkeypatch.setattr("eodinga.content.registry.get_spec_for", patched_get_spec_for)

    rebuild_index(db_path, [RootConfig(path=root)], content_enabled=True)

    with open_index(db_path) as conn:
        result = search(conn, "report")
    assert result.total_estimate >= 1

    service = WatchService()
    service.record(WatchEvent(event_type="created", path=root / "live.txt"))

    metrics = snapshot_metrics()
    counters = cast(dict[str, int], metrics["counters"])
    histograms = cast(dict[str, dict[str, object]], metrics["histograms"])
    assert counters["files_indexed"] == 3
    assert counters["parser_errors"] == 1
    assert counters["queries_served"] == 1
    assert counters["watcher_events"] == 1
    assert counters["parsers.broken.error"] == 1
    assert histograms["query_latency_ms"]["count"] == 1
