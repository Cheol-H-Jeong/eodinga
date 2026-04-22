from __future__ import annotations

import json
from pathlib import Path

from eodinga.__main__ import main
from eodinga.common import WatchEvent
from eodinga.content.base import ParserSpec
from eodinga.content.registry import parse
from eodinga.core.watcher import WatchService
from eodinga.observability import (
    configure_logging,
    default_log_dir,
    get_logger,
    metrics_snapshot,
    reset_metrics,
    write_crash_report,
)


def test_stats_json_reports_runtime_counters_and_db_snapshot(
    tmp_path: Path, capsys
) -> None:
    reset_metrics()
    root = tmp_path / "docs"
    root.mkdir()
    (root / "alpha.txt").write_text("launcher note\n", encoding="utf-8")
    db_path = tmp_path / "index.db"

    assert main(["--db", str(db_path), "index", "--root", str(root), "--rebuild"]) == 0
    capsys.readouterr()

    assert main(["--db", str(db_path), "search", "launcher", "--json"]) == 0
    capsys.readouterr()

    assert main(["--db", str(db_path), "stats", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["files_indexed"] >= 1
    assert payload["documents_indexed"] >= 1
    assert payload["db_path"] == str(db_path)
    assert payload["counters"]["files_indexed"] >= 1
    assert payload["counters"]["queries_served"] == 1
    assert sum(payload["query_latency_histogram"].values()) == 1


def test_parser_errors_increment_global_counter(monkeypatch, tmp_path: Path) -> None:
    reset_metrics()
    target = tmp_path / "broken.txt"
    target.write_text("boom\n", encoding="utf-8")

    def failing_parse(path: Path, max_body_chars: int):
        raise RuntimeError(f"failed {path} {max_body_chars}")

    spec = ParserSpec(
        name="broken",
        extensions=frozenset({"txt"}),
        parse=failing_parse,
        max_bytes=1024,
    )
    monkeypatch.setattr("eodinga.content.registry.load_specs", lambda: (spec,))

    parsed = parse(target, max_body_chars=256)
    counters, _ = metrics_snapshot()

    assert parsed.body_text == ""
    assert counters["parser_errors"] == 1
    assert counters["parsers.broken.error"] == 1


def test_watcher_events_increment_counter(tmp_path: Path) -> None:
    reset_metrics()
    service = WatchService()
    service.record(WatchEvent(event_type="created", path=tmp_path / "note.txt"))

    counters, _ = metrics_snapshot()

    assert counters["watcher_events"] == 1


def test_default_log_dir_uses_xdg_state_home(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    assert default_log_dir() == tmp_path / "state" / "eodinga"


def test_configure_logging_writes_rotating_log_file(tmp_path: Path) -> None:
    reset_metrics()
    log_path = tmp_path / "logs" / "eodinga.log"

    configure_logging("INFO", log_path=log_path)
    get_logger("test").info("log line")

    assert log_path.exists()
    assert "log line" in log_path.read_text(encoding="utf-8")


def test_write_crash_report_creates_json_payload(tmp_path: Path) -> None:
    try:
        raise RuntimeError("boom")
    except RuntimeError as error:
        report_path = write_crash_report(
            type(error),
            error,
            error.__traceback__,
            log_dir=tmp_path,
        )

    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert report_path.name.startswith("crash-")
    assert payload["type"] == "RuntimeError"
    assert payload["message"] == "boom"
