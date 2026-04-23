from __future__ import annotations

import argparse
import json
import os
import re
import sys
from contextlib import closing
from pathlib import Path
from time import monotonic
from typing import Any

from eodinga import __version__
from eodinga.common import SearchResult, StatsSnapshot
from eodinga.config import AppConfig, RootConfig, load
from eodinga.doctor import run_diagnostics
from eodinga.index.build import rebuild_index
from eodinga.index.reader import stats as read_index_stats
from eodinga.index.storage import open_index
from eodinga.observability import (
    configure_logging,
    counter_value,
    file_logging_enabled,
    histogram_snapshot,
    increment_counter,
    install_crash_handlers,
    record_snapshot,
    record_histogram,
    recent_snapshots,
    resolve_crash_dir,
    snapshot_metrics,
    report_crash,
    resolve_log_compression,
    resolve_log_target,
    resolve_log_retention,
    resolve_log_rotation,
)
from eodinga.query import QuerySyntaxError, search as run_search


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="eodinga")
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--db", type=Path)

    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser("index")
    index_parser.add_argument("--root", type=Path, action="append")
    index_parser.add_argument("--rebuild", action="store_true")
    index_parser.set_defaults(handler=_cmd_index)

    watch_parser = subparsers.add_parser("watch")
    watch_parser.set_defaults(handler=_cmd_watch)

    search_parser = subparsers.add_parser("search")
    search_parser.add_argument("query")
    search_parser.add_argument("--json", action="store_true")
    search_parser.add_argument("--limit", type=int, default=200)
    search_parser.add_argument("--root", type=Path)
    search_parser.set_defaults(handler=_cmd_search)

    stats_parser = subparsers.add_parser("stats")
    stats_parser.add_argument("--json", action="store_true")
    stats_parser.set_defaults(handler=_cmd_stats)

    gui_parser = subparsers.add_parser("gui")
    gui_parser.add_argument("--test-mode", action="store_true")
    gui_parser.set_defaults(handler=_cmd_gui)

    doctor_parser = subparsers.add_parser("doctor")
    doctor_parser.set_defaults(handler=_cmd_doctor)

    version_parser = subparsers.add_parser("version")
    version_parser.set_defaults(handler=_cmd_version)
    return parser


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    raise TypeError(f"Unsupported JSON type: {type(value)!r}")


def _emit(payload: Any, as_json: bool = False) -> int:
    if as_json:
        sys.stdout.write(json.dumps(payload, default=_json_default))
        sys.stdout.write("\n")
        return 0
    sys.stdout.write(f"{payload}\n")
    return 0


def _resolve_config(args: argparse.Namespace) -> AppConfig:
    return load(args.config)


def _normalize_search_root(root: Path | None) -> Path | None:
    if root is None:
        return None
    root_text = str(root)
    if re.match(r"^[A-Za-z]:[\\/]", root_text) or root_text.startswith("\\\\"):
        return Path(root_text)
    return root.resolve()


def _resolve_index_roots(args: argparse.Namespace, config: AppConfig) -> list[RootConfig]:
    if args.root:
        return [RootConfig(path=path) for path in args.root]
    return list(config.roots)


def _cmd_index(args: argparse.Namespace) -> int:
    config = _resolve_config(args)
    roots = _resolve_index_roots(args, config)
    if not roots:
        sys.stderr.write("index rebuild requires at least one root\n")
        return 2
    result = rebuild_index(
        args.db or config.index.db_path,
        roots,
        content_enabled=config.index.content_enabled,
    )
    payload = {
        "command": "index",
        "rebuild": bool(args.rebuild),
        "db": str(result.db_path),
        "roots": [str(root.path) for root in roots],
        "files_indexed": result.files_indexed,
    }
    record_snapshot(
        "command.index",
        {
            "db": str(result.db_path),
            "roots": payload["roots"],
            "files_indexed": result.files_indexed,
            "rebuild": bool(args.rebuild),
        },
    )
    return _emit(payload, as_json=True)


def _cmd_watch(args: argparse.Namespace) -> int:
    payload = {"command": "watch", "db": str(args.db) if args.db else None}
    record_snapshot("command.watch", payload)
    return _emit(payload, as_json=True)


def _cmd_search(args: argparse.Namespace) -> int:
    _resolve_config(args)
    limit = max(int(args.limit), 0)
    root = _normalize_search_root(args.root)
    try:
        with closing(open_index(args.db or _resolve_config(args).index.db_path)) as conn:
            query_result = run_search(conn, args.query, limit=limit, root=root)
    except (QuerySyntaxError, ValueError) as error:
        sys.stderr.write(f"{error}\n")
        return 2

    hits = query_result.hits
    results = [
        SearchResult(
            path=hit.file.path,
            score=hit.match_score,
            snippet=hit.snippet,
        ).model_dump(mode="json")
        for hit in hits[:limit]
    ]
    payload = {
        "query": args.query,
        "results": results,
        "count": query_result.total_estimate,
        "returned": len(results),
        "elapsed_ms": query_result.elapsed_ms,
    }
    record_snapshot(
        "command.search",
        {
            "query": args.query,
            "count": query_result.total_estimate,
            "returned": len(results),
            "elapsed_ms": query_result.elapsed_ms,
            "limit": limit,
            "root": str(root) if root is not None else None,
        },
    )
    return _emit(payload, as_json=bool(args.json))


def _cmd_stats(args: argparse.Namespace) -> int:
    config = _resolve_config(args)
    db_path = args.db or config.index.db_path
    with closing(open_index(db_path)) as conn:
        index_snapshot = read_index_stats(conn)
    metrics = snapshot_metrics()
    counters = metrics["counters"]
    log_target = resolve_log_target()
    snapshot = StatsSnapshot(
        generated_at=metrics["generated_at"],
        process_started_at=metrics["process_started_at"],
        pid=int(metrics["pid"]),
        thread_count=int(metrics["thread_count"]),
        rss_bytes=metrics["rss_bytes"],
        open_fd_count=metrics["open_fd_count"],
        version=str(metrics["version"]),
        uptime_ms=float(metrics["uptime_ms"]),
        files_indexed=index_snapshot.file_count,
        documents_indexed=index_snapshot.content_count,
        queries_served=counter_value("queries_served"),
        queries_zero_results=counter_value("queries_zero_results"),
        queries_truncated=counter_value("queries_truncated"),
        parser_errors=counter_value("parser_errors"),
        watcher_events=counter_value("watcher_events"),
        watcher_flushes=counter_value("watcher_flushes"),
        watcher_events_flushed=counter_value("watcher_events_flushed"),
        watcher_queue_full=counter_value("watcher_queue_full"),
        watcher_enqueue_aborted=counter_value("watcher_enqueue_aborted"),
        watcher_observers_started=counter_value("watcher_observers_started"),
        watcher_observers_stopped=counter_value("watcher_observers_stopped"),
        watcher_observer_failures=counter_value("watcher_observer_failures"),
        watcher_observer_cleanup_failures=counter_value("watcher_observer_cleanup_failures"),
        watcher_startup_rollbacks=counter_value("watcher_startup_rollbacks"),
        index_rebuilds_completed=counter_value("index_rebuilds_completed"),
        commands_started=counter_value("commands_started"),
        commands_completed=counter_value("commands_completed"),
        commands_failed=counter_value("commands_failed"),
        commands_interrupted=counter_value("commands_interrupted"),
        crashes_reported=counter_value("crashes_reported"),
        crash_logs_written=counter_value("crash_logs_written"),
        crash_log_write_failures=counter_value("crash_log_write_failures"),
        crash_handlers_installed=counter_value("crash_handlers_installed"),
        logging_configurations=counter_value("logging_configurations"),
        log_sinks_stderr_configured=counter_value("log_sinks.stderr.configured"),
        log_sinks_file_configured=counter_value("log_sinks.file.configured"),
        log_sinks_file_disabled=counter_value("log_sinks.file.disabled"),
        query_latency_histogram=histogram_snapshot("query_latency_ms"),
        query_result_count_histogram=histogram_snapshot("query_result_count"),
        command_latency_histogram=histogram_snapshot("command_latency_ms"),
        watch_flush_batch_histogram=histogram_snapshot("watch_flush_batch_size"),
        watch_event_lag_histogram=histogram_snapshot("watch_event_lag_ms"),
        watcher_queue_backpressure_histogram=histogram_snapshot("watcher_queue_backpressure_ms"),
        index_rebuild_latency_histogram=histogram_snapshot("index_rebuild_latency_ms"),
        index_batch_size_histogram=histogram_snapshot("index_batch_size"),
        commands=_command_summary(counters),
        exit_codes=_exit_code_summary(counters),
        crash_types=_crash_type_summary(counters),
        parser_activity=_parser_activity_summary(counters),
        parser_resolution=_parser_resolution_summary(counters),
        watcher_event_types=_watcher_event_type_summary(counters),
        watcher_failure_stages=_watcher_failure_stage_summary(counters),
        watcher_cleanup_failure_stages=_watcher_cleanup_failure_stage_summary(counters),
        counters=counters,
        histograms=metrics["histograms"],
        recent_snapshots=[dict(entry) for entry in recent_snapshots()],
        roots=list(index_snapshot.roots) or [root.path for root in config.roots],
        db_path=db_path,
        log_path=log_target.path,
        log_path_source=log_target.source,
        log_path_disabled_reason=log_target.disabled_reason,
        log_sink_sources=_log_sink_source_summary(counters),
        log_sink_disabled_reasons=_log_sink_disabled_reason_summary(counters),
        log_rotation=resolve_log_rotation(),
        log_retention=resolve_log_retention(),
        log_compression=resolve_log_compression(),
        crash_dir=resolve_crash_dir(),
        file_logging_enabled=file_logging_enabled(),
    ).model_dump(mode="json")
    record_snapshot(
        "command.stats",
        {
            "db": str(db_path),
            "files_indexed": snapshot["files_indexed"],
            "documents_indexed": snapshot["documents_indexed"],
            "queries_served": snapshot["queries_served"],
            "commands_started": snapshot["commands_started"],
        },
    )
    return _emit(snapshot, as_json=bool(args.json))


def _cmd_gui(args: argparse.Namespace) -> int:
    from eodinga.gui.app import launch_gui

    test_mode = bool(args.test_mode) or os.environ.get("QT_QPA_PLATFORM") == "offscreen"
    config = _resolve_config(args)
    db_path = args.db or config.index.db_path
    if test_mode:
        launched = launch_gui(test_mode=True, db_path=db_path, config=config, config_path=args.config)
        app, window, launcher = launched
        launcher.close()
        window.close()
        app.processEvents()
        return 0
    return int(launch_gui(test_mode=False, db_path=db_path, config=config, config_path=args.config))


def _cmd_doctor(args: argparse.Namespace) -> int:
    config = _resolve_config(args)
    report, exit_code = run_diagnostics(config=config, db_path=args.db)
    record_snapshot(
        "command.doctor",
        {
            "db": str(args.db) if args.db else None,
            "exit_code": exit_code,
            "checks": len(report.get("checks", [])) if isinstance(report, dict) else 0,
        },
    )
    _emit(report, as_json=True)
    return exit_code


def _cmd_version(args: argparse.Namespace) -> int:
    record_snapshot("command.version", {"version": __version__})
    return _emit(__version__)


def _run_command(args: argparse.Namespace) -> int:
    command = args.command or "<interactive>"
    increment_counter("commands_started", command=command)
    increment_counter(f"commands.{command}.started")
    started_at = monotonic()
    exit_code: int | None = None
    failure_reason: str | None = None
    try:
        exit_code = int(args.handler(args))
    except KeyboardInterrupt:
        exit_code = 130
        failure_reason = "interrupted"
        increment_counter("commands_interrupted", command=command)
        increment_counter(f"commands.{command}.interrupted")
    except Exception:
        exit_code = 1
        failure_reason = "exception"
        increment_counter("commands_failed", command=command)
        increment_counter(f"commands.{command}.failed")
        raise
    finally:
        elapsed_ms = max((monotonic() - started_at) * 1000, 0.0)
        record_histogram("command_latency_ms", elapsed_ms, command=command)
        if exit_code is not None:
            increment_counter(f"commands.exit_code.{exit_code}")
            if exit_code != 0:
                record_snapshot(
                    "command.failure",
                    {
                        "command": command,
                        "exit_code": exit_code,
                        "reason": failure_reason or "nonzero_exit",
                        "elapsed_ms": round(elapsed_ms, 3),
                    },
                )
    assert exit_code is not None
    if exit_code == 0:
        increment_counter("commands_completed", command=command)
        increment_counter(f"commands.{command}.completed")
    elif exit_code != 130:
        increment_counter("commands_failed", command=command)
        increment_counter(f"commands.{command}.failed")
    return exit_code


def _command_summary(counters: dict[str, int]) -> dict[str, dict[str, int]]:
    commands: dict[str, dict[str, int]] = {}
    prefix = "commands."
    for name, value in counters.items():
        if not name.startswith(prefix) or name.startswith("commands.exit_code."):
            continue
        command_name, _, status = name[len(prefix) :].rpartition(".")
        if not command_name or status not in {"started", "completed", "failed", "interrupted"}:
            continue
        commands.setdefault(command_name, {})[status] = value
    return dict(sorted((name, dict(sorted(statuses.items()))) for name, statuses in commands.items()))


def _exit_code_summary(counters: dict[str, int]) -> dict[str, int]:
    prefix = "commands.exit_code."
    exit_codes = {
        name[len(prefix) :]: value for name, value in counters.items() if name.startswith(prefix)
    }
    return dict(sorted(exit_codes.items(), key=lambda item: int(item[0])))


def _crash_type_summary(counters: dict[str, int]) -> dict[str, int]:
    prefix = "crashes."
    crash_types = {
        name[len(prefix) :]: value
        for name, value in counters.items()
        if name.startswith(prefix)
    }
    return dict(sorted(crash_types.items()))


def _parser_activity_summary(counters: dict[str, int]) -> dict[str, dict[str, int]]:
    parser_activity: dict[str, dict[str, int]] = {}
    prefix = "parsers."
    for name, value in counters.items():
        if not name.startswith(prefix):
            continue
        parser_name, _, status = name[len(prefix) :].rpartition(".")
        if not parser_name or status not in {"error", "parsed", "skipped_too_large"}:
            continue
        if status == "error":
            key = "errors"
        elif status == "parsed":
            key = "parsed"
        else:
            key = "skipped_too_large"
        parser_activity.setdefault(parser_name, {})[key] = value
    return dict(
        sorted((name, dict(sorted(statuses.items()))) for name, statuses in parser_activity.items())
    )


def _parser_resolution_summary(counters: dict[str, int]) -> dict[str, int]:
    keys = ("entrypoint_load_error", "no_extension", "unsupported_extension")
    parser_resolution = {
        key: counters[f"parsers.{key}"] for key in keys if f"parsers.{key}" in counters
    }
    return dict(sorted(parser_resolution.items()))


def _watcher_event_type_summary(counters: dict[str, int]) -> dict[str, int]:
    prefix = "watcher_events."
    event_types = {
        name[len(prefix) :]: value
        for name, value in counters.items()
        if name.startswith(prefix)
    }
    return dict(sorted(event_types.items()))


def _watcher_failure_stage_summary(counters: dict[str, int]) -> dict[str, int]:
    prefix = "watcher_observer_failures."
    stages = {
        name[len(prefix) :]: value for name, value in counters.items() if name.startswith(prefix)
    }
    return dict(sorted(stages.items()))


def _watcher_cleanup_failure_stage_summary(counters: dict[str, int]) -> dict[str, int]:
    prefix = "watcher_observer_cleanup_failures."
    stages = {
        name[len(prefix) :]: value for name, value in counters.items() if name.startswith(prefix)
    }
    return dict(sorted(stages.items()))


def _log_sink_source_summary(counters: dict[str, int]) -> dict[str, int]:
    prefix = "log_sinks.file.source."
    sources = {
        name[len(prefix) :]: value for name, value in counters.items() if name.startswith(prefix)
    }
    return dict(sorted(sources.items()))


def _log_sink_disabled_reason_summary(counters: dict[str, int]) -> dict[str, int]:
    prefix = "log_sinks.file.disabled."
    reasons = {
        name[len(prefix) :]: value for name, value in counters.items() if name.startswith(prefix)
    }
    return dict(sorted(reasons.items()))


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.log_level)
    install_crash_handlers()
    try:
        return _run_command(args)
    except KeyboardInterrupt:
        raise
    except Exception as error:
        command_argv = argv or sys.argv[1:]
        command = " ".join(command_argv) or "<interactive>"
        crash_path = report_crash(
            error,
            context=f"Unhandled exception while running: {command}",
            details={"argv": command_argv},
        )
        record_snapshot(
            "command.crash",
            {
                "command": command,
                "error_type": type(error).__name__,
                "crash_path": str(crash_path) if crash_path is not None else None,
            },
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
