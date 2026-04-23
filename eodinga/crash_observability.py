from __future__ import annotations

import os
import sys
import threading
import traceback
from collections.abc import Mapping
from json import dumps as json_dumps
from pathlib import Path
from typing import IO, Any


def default_crash_dir() -> Path:
    from eodinga.observability import default_logs_dir, default_state_dir

    if sys.platform == "darwin":
        return default_logs_dir() / "crashes"
    return default_state_dir() / "crashes"


def resolve_crash_dir(crash_dir: Path | None = None) -> Path:
    if crash_dir is not None:
        return crash_dir.expanduser()
    override_dir = os.environ.get("EODINGA_CRASH_DIR")
    if override_dir:
        return Path(override_dir).expanduser()
    return default_crash_dir()


def write_crash_log(
    error: BaseException,
    *,
    crash_dir: Path | None = None,
    context: str = "Unhandled exception",
    details: Mapping[str, object] | None = None,
) -> Path:
    from eodinga.observability import (
        file_logging_enabled,
        increment_counter,
        recent_snapshots,
        resolve_log_compression,
        resolve_log_path,
        resolve_log_retention,
        resolve_log_rotation,
        snapshot_metrics,
    )

    target_dir = resolve_crash_dir(crash_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    metrics = snapshot_metrics()
    timestamp = metrics["generated_at"].replace(":", "").replace("-", "")
    crash_path = _next_crash_path(target_dir, timestamp)
    metadata: dict[str, object] = {
        "timestamp": timestamp,
        "process_started_at": metrics["process_started_at"],
        "uptime_ms": metrics["uptime_ms"],
        "pid": metrics["pid"],
        "thread_count": metrics["thread_count"],
        "rss_bytes": metrics["rss_bytes"],
        "open_fd_count": metrics["open_fd_count"],
        "version": metrics["version"],
        "platform": sys.platform,
        "python": sys.version.split()[0],
        "thread": threading.current_thread().name,
        "executable": sys.executable,
        "argv": sys.argv[1:],
        "cwd": str(Path.cwd()),
        "file_logging_enabled": file_logging_enabled(),
        "log_path": resolve_log_path(),
        "log_rotation": resolve_log_rotation(),
        "log_retention": resolve_log_retention(),
        "log_compression": resolve_log_compression(),
        "crash_dir": target_dir,
        "metrics_generated_at": metrics["generated_at"],
        "metrics_counters": metrics["counters"],
        "metrics_histograms": metrics["histograms"],
        "recent_snapshots": recent_snapshots(),
    }
    if details:
        metadata.update(details)
    lines = [
        f"{context}\n",
        *[f"{key}={_format_detail_value(value)}\n" for key, value in metadata.items()],
        f"{type(error).__name__}: {error}\n",
        "\n",
        *traceback.format_exception(type(error), error, error.__traceback__),
    ]
    crash_path.write_text("".join(lines), encoding="utf-8")
    increment_counter("crash_logs_written")
    return crash_path


def install_crash_handlers(*, stream: IO[str] | None = None) -> None:
    from eodinga.observability import increment_counter, report_crash

    increment_counter("crash_handlers_installed")

    def _handle_exception(
        exc_type: type[BaseException],
        error: BaseException,
        tb: Any,
    ) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            return
        error.__traceback__ = tb
        report_crash(error, context="Unhandled top-level exception", stream=stream)

    def _handle_thread_exception(args: threading.ExceptHookArgs) -> None:
        if args.exc_value is None or isinstance(args.exc_value, KeyboardInterrupt):
            return
        details = {"thread": args.thread.name if args.thread is not None else None}
        report_crash(
            args.exc_value,
            context="Unhandled thread exception",
            details=details,
            stream=stream,
        )

    def _handle_unraisable(args: sys.UnraisableHookArgs) -> None:
        if args.exc_value is None or isinstance(args.exc_value, KeyboardInterrupt):
            return
        details = {
            "object": repr(args.object) if args.object is not None else None,
            "err_msg": args.err_msg,
        }
        report_crash(
            args.exc_value,
            context="Unhandled unraisable exception",
            details=details,
            stream=stream,
        )

    sys.excepthook = _handle_exception
    threading.excepthook = _handle_thread_exception
    sys.unraisablehook = _handle_unraisable


def _next_crash_path(target_dir: Path, timestamp: str) -> Path:
    candidate = target_dir / f"crash-{timestamp}.log"
    if not candidate.exists():
        return candidate
    suffix = 1
    while True:
        candidate = target_dir / f"crash-{timestamp}-{suffix}.log"
        if not candidate.exists():
            return candidate
        suffix += 1


def _format_detail_value(value: object) -> str:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return str(value)
    return json_dumps(value, sort_keys=True)
