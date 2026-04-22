from __future__ import annotations

import json
import os
import sys
import threading
from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger

_COUNTERS_LOCK = threading.Lock()
_COUNTERS: Counter[str] = Counter()
_QUERY_LATENCY_BUCKETS = (
    (1.0, "le_1ms"),
    (5.0, "le_5ms"),
    (10.0, "le_10ms"),
    (25.0, "le_25ms"),
    (50.0, "le_50ms"),
    (100.0, "le_100ms"),
    (250.0, "le_250ms"),
    (500.0, "le_500ms"),
)
_QUERY_LATENCY_HISTOGRAM: Counter[str] = Counter()


def default_log_dir() -> Path:
    if sys.platform.startswith("win"):
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            return Path(local_appdata) / "eodinga" / "logs"
        return Path.home() / "AppData" / "Local" / "eodinga" / "logs"
    xdg_state = os.environ.get("XDG_STATE_HOME")
    if xdg_state:
        return Path(xdg_state) / "eodinga"
    return Path.home() / ".local" / "state" / "eodinga"


def default_log_path() -> Path:
    return default_log_dir() / "eodinga.log"


def configure_logging(level: str = "INFO", log_path: Path | None = None) -> None:
    logger.remove()
    logger.add(sys.stderr, level=level.upper())
    resolved_log_path = (log_path or default_log_path()).expanduser()
    resolved_log_path.parent.mkdir(parents=True, exist_ok=True)
    logger.add(
        resolved_log_path,
        rotation="5 MB",
        retention=5,
        level=level.upper(),
    )


def get_logger(name: str | None = None) -> Any:
    return logger.bind(component=name or "eodinga")


def increment_counter(name: str, value: int = 1, **fields: object) -> None:
    del fields
    with _COUNTERS_LOCK:
        _COUNTERS[name] += value


def record_counter(name: str, value: int = 1, **fields: object) -> None:
    increment_counter(name, value=value, **fields)


def record_snapshot(name: str, payload: Mapping[str, object]) -> None:
    del name
    del payload


def observe_query_latency(elapsed_ms: float) -> None:
    bucket = "gt_500ms"
    for upper_bound, label in _QUERY_LATENCY_BUCKETS:
        if elapsed_ms <= upper_bound:
            bucket = label
            break
    with _COUNTERS_LOCK:
        _QUERY_LATENCY_HISTOGRAM[bucket] += 1


def metrics_snapshot() -> tuple[dict[str, int], dict[str, int]]:
    with _COUNTERS_LOCK:
        return dict(_COUNTERS), dict(_QUERY_LATENCY_HISTOGRAM)


def reset_metrics() -> None:
    with _COUNTERS_LOCK:
        _COUNTERS.clear()
        _QUERY_LATENCY_HISTOGRAM.clear()


def write_crash_report(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_traceback: Any,
    *,
    log_dir: Path | None = None,
) -> Path:
    target_dir = (log_dir or default_log_dir()).expanduser()
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    report_path = target_dir / f"crash-{timestamp}.log"
    payload = {
        "timestamp": timestamp,
        "type": exc_type.__name__,
        "message": str(exc_value),
    }
    report_path.write_text(f"{json.dumps(payload)}\n", encoding="utf-8")
    logger.opt(exception=(exc_type, exc_value, exc_traceback)).critical(
        "Unhandled exception recorded at {}",
        report_path,
    )
    return report_path


def install_crash_handler(log_dir: Path | None = None) -> None:
    original_hook = sys.excepthook

    def _handle_exception(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback: Any,
    ) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            original_hook(exc_type, exc_value, exc_traceback)
            return
        write_crash_report(
            exc_type,
            exc_value,
            exc_traceback,
            log_dir=log_dir,
        )
        original_hook(exc_type, exc_value, exc_traceback)

    sys.excepthook = _handle_exception

    def _thread_hook(args: threading.ExceptHookArgs) -> None:
        if args.exc_value is None:
            return
        _handle_exception(args.exc_type, args.exc_value, args.exc_traceback)

    threading.excepthook = _thread_hook
