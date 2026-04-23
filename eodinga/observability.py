from __future__ import annotations

import os
import sys
import threading
import traceback
from collections import deque
from dataclasses import dataclass, field
from collections.abc import Mapping
from datetime import UTC, datetime
from json import dumps as json_dumps
from pathlib import Path
from threading import Lock
from typing import IO, Any, cast, TypedDict

from loguru import logger

from eodinga.metrics_store import delete_metrics_state, load_metrics_state, save_metrics_state

try:
    import resource
except ImportError:  # pragma: no cover - unavailable on Windows
    resource = None

_DEFAULT_HISTOGRAM_BUCKETS_MS = (1.0, 5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0)
_DEFAULT_LOG_ROTATION: str | int = "5 MB"
_DEFAULT_LOG_RETENTION: str | int = 5
_RECENT_SNAPSHOT_LIMIT = 20
_METRICS_LOCK = Lock()
_COUNTERS: dict[str, int] = {}
_HISTOGRAMS: dict[str, _HistogramState] = {}
_PROCESS_STARTED_AT = datetime.now(UTC)
_METRICS_LOADED = False


@dataclass
class _HistogramState:
    buckets_ms: tuple[float, ...]
    count: int = 0
    sum_ms: float = 0.0
    min_ms: float | None = None
    max_ms: float | None = None
    bucket_hits: dict[str, int] = field(default_factory=dict)

    def observe(self, value_ms: float) -> None:
        self.count += 1
        self.sum_ms += value_ms
        self.min_ms = value_ms if self.min_ms is None else min(self.min_ms, value_ms)
        self.max_ms = value_ms if self.max_ms is None else max(self.max_ms, value_ms)
        label = _bucket_label(value_ms, self.buckets_ms)
        self.bucket_hits[label] = self.bucket_hits.get(label, 0) + 1

    def snapshot(self) -> dict[str, object]:
        return {
            "bounds_ms": list(self.buckets_ms),
            "count": self.count,
            "sum_ms": round(self.sum_ms, 3),
            "min_ms": round(self.min_ms, 3) if self.min_ms is not None else None,
            "max_ms": round(self.max_ms, 3) if self.max_ms is not None else None,
            "buckets": dict(sorted(self.bucket_hits.items())),
        }

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, object]) -> _HistogramState:
        bounds = snapshot.get("bounds_ms")
        buckets = snapshot.get("buckets")
        if not isinstance(bounds, list) or not all(isinstance(item, (int, float)) for item in bounds):
            raise ValueError("persisted histogram bounds are invalid")
        if not isinstance(buckets, dict) or not all(
            isinstance(label, str) and isinstance(count, int) for label, count in buckets.items()
        ):
            raise ValueError("persisted histogram buckets are invalid")
        count = snapshot.get("count")
        sum_ms = snapshot.get("sum_ms")
        min_ms = snapshot.get("min_ms")
        max_ms = snapshot.get("max_ms")
        if not isinstance(count, int) or not isinstance(sum_ms, (int, float)):
            raise ValueError("persisted histogram summary is invalid")
        if min_ms is not None and not isinstance(min_ms, (int, float)):
            raise ValueError("persisted histogram min is invalid")
        if max_ms is not None and not isinstance(max_ms, (int, float)):
            raise ValueError("persisted histogram max is invalid")
        return cls(
            buckets_ms=tuple(float(item) for item in bounds),
            count=count,
            sum_ms=float(sum_ms),
            min_ms=None if min_ms is None else float(min_ms),
            max_ms=None if max_ms is None else float(max_ms),
            bucket_hits=dict(sorted(buckets.items())),
        )


class MetricsSnapshot(TypedDict):
    counters: dict[str, int]
    histograms: dict[str, dict[str, object]]
    generated_at: str
    open_fd_count: int | None
    process_started_at: str
    pid: int
    rss_bytes: int | None
    thread_count: int
    version: str
    uptime_ms: float


class SnapshotRecord(TypedDict):
    name: str
    recorded_at: str
    payload: dict[str, object]


_RECENT_SNAPSHOTS: deque[SnapshotRecord] = deque(maxlen=_RECENT_SNAPSHOT_LIMIT)


def _bucket_label(value_ms: float, buckets_ms: tuple[float, ...]) -> str:
    for upper_bound in buckets_ms:
        if value_ms <= upper_bound:
            return f"<= {upper_bound:g}ms"
    return f"> {buckets_ms[-1]:g}ms"


def default_state_dir() -> Path:
    if sys.platform.startswith("win"):
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            return Path(local_appdata) / "eodinga"
        return Path.home() / "AppData" / "Local" / "eodinga"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "eodinga"
    xdg_state = os.environ.get("XDG_STATE_HOME")
    if xdg_state:
        return Path(xdg_state) / "eodinga"
    return Path.home() / ".local" / "state" / "eodinga"


def default_logs_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / "eodinga"
    return default_state_dir() / "logs"


def default_log_path() -> Path:
    return default_logs_dir() / "eodinga.log"


def default_crash_dir() -> Path:
    if sys.platform == "darwin":
        return default_logs_dir() / "crashes"
    return default_state_dir() / "crashes"


def file_logging_enabled() -> bool:
    return os.environ.get("EODINGA_DISABLE_FILE_LOGGING") != "1"


def resolve_log_path(log_path: Path | None = None) -> Path | None:
    if not file_logging_enabled():
        return None
    if log_path is not None:
        return log_path.expanduser()
    override_path = os.environ.get("EODINGA_LOG_PATH")
    if override_path:
        return Path(override_path).expanduser()
    if "PYTEST_CURRENT_TEST" in os.environ:
        return None
    return default_log_path()


def resolve_metrics_path(metrics_path: Path | None = None) -> Path | None:
    if metrics_path is not None:
        return metrics_path.expanduser()
    if os.environ.get("EODINGA_DISABLE_METRICS_PERSISTENCE") == "1":
        return None
    override_path = os.environ.get("EODINGA_METRICS_PATH")
    if override_path:
        return Path(override_path).expanduser()
    if "PYTEST_CURRENT_TEST" in os.environ:
        return None
    return default_state_dir() / "metrics.json"


def metrics_persistence_enabled(metrics_path: Path | None = None) -> bool:
    return resolve_metrics_path(metrics_path) is not None


def resolve_crash_dir(crash_dir: Path | None = None) -> Path:
    if crash_dir is not None:
        return crash_dir.expanduser()
    override_dir = os.environ.get("EODINGA_CRASH_DIR")
    if override_dir:
        return Path(override_dir).expanduser()
    return default_crash_dir()


def resolve_log_rotation() -> str | int:
    override = os.environ.get("EODINGA_LOG_ROTATION")
    if not override:
        return _DEFAULT_LOG_ROTATION
    return _parse_log_policy_value(override)


def resolve_log_retention() -> str | int:
    override = os.environ.get("EODINGA_LOG_RETENTION")
    if not override:
        return _DEFAULT_LOG_RETENTION
    return _parse_log_policy_value(override)


def resolve_log_compression() -> str | None:
    override = os.environ.get("EODINGA_LOG_COMPRESSION")
    if override is None:
        return None
    compression = override.strip()
    return compression or None


def configure_logging(level: str = "INFO", log_path: Path | None = None) -> None:
    _ensure_metrics_loaded()
    logger.remove()
    logger.add(sys.stderr, level=level.upper())
    increment_counter("logging_configurations")
    increment_counter("log_sinks.stderr.configured")
    target = resolve_log_path(log_path)
    if target is None:
        increment_counter("log_sinks.file.disabled")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    logger.add(
        target,
        rotation=resolve_log_rotation(),
        retention=resolve_log_retention(),
        compression=resolve_log_compression(),
        encoding="utf-8",
        delay=True,
        backtrace=False,
        diagnose=False,
        level=level.upper(),
    )
    increment_counter("log_sinks.file.configured")


def get_logger(name: str | None = None) -> Any:
    return logger.bind(component=name or "eodinga")


def increment_counter(name: str, value: int = 1, **fields: object) -> None:
    _ensure_metrics_loaded()
    with _METRICS_LOCK:
        _COUNTERS[name] = _COUNTERS.get(name, 0) + value
        _persist_metrics_unlocked()
    logger.bind(metric=name, **fields).debug("counter +{value}", value=value)


def record_counter(name: str, value: int = 1, **fields: object) -> None:
    increment_counter(name, value=value, **fields)


def record_histogram(
    name: str,
    value_ms: float,
    *,
    buckets_ms: tuple[float, ...] = _DEFAULT_HISTOGRAM_BUCKETS_MS,
    **fields: object,
) -> None:
    _ensure_metrics_loaded()
    with _METRICS_LOCK:
        state = _HISTOGRAMS.get(name)
        if state is None:
            state = _HistogramState(buckets_ms=buckets_ms)
            _HISTOGRAMS[name] = state
        state.observe(value_ms)
        _persist_metrics_unlocked()
    logger.bind(metric=name, **fields).debug("histogram {value_ms:.3f}ms", value_ms=value_ms)


def snapshot_metrics() -> MetricsSnapshot:
    from eodinga import __version__

    _ensure_metrics_loaded()
    with _METRICS_LOCK:
        counters = dict(sorted(_COUNTERS.items()))
        histograms: dict[str, dict[str, object]] = {
            name: state.snapshot() for name, state in sorted(_HISTOGRAMS.items())
        }
    now = datetime.now(UTC)
    return {
        "counters": counters,
        "histograms": histograms,
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "open_fd_count": _open_fd_count(),
        "process_started_at": _PROCESS_STARTED_AT.isoformat().replace("+00:00", "Z"),
        "pid": os.getpid(),
        "rss_bytes": _rss_bytes(),
        "thread_count": threading.active_count(),
        "version": __version__,
        "uptime_ms": round((now - _PROCESS_STARTED_AT).total_seconds() * 1000, 3),
    }


def reset_metrics() -> None:
    global _METRICS_LOADED
    path = resolve_metrics_path()
    with _METRICS_LOCK:
        _COUNTERS.clear()
        _HISTOGRAMS.clear()
        _RECENT_SNAPSHOTS.clear()
        _METRICS_LOADED = False
    if path is not None:
        delete_metrics_state(path)


def record_snapshot(name: str, payload: Mapping[str, object]) -> None:
    _ensure_metrics_loaded()
    record: SnapshotRecord = {
        "name": name,
        "recorded_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "payload": dict(payload),
    }
    with _METRICS_LOCK:
        _RECENT_SNAPSHOTS.append(record)
        _persist_metrics_unlocked()
    logger.bind(metric=name, payload=record["payload"]).debug("snapshot recorded")


def recent_snapshots() -> list[SnapshotRecord]:
    _ensure_metrics_loaded()
    with _METRICS_LOCK:
        return list(_RECENT_SNAPSHOTS)


def counter_value(name: str) -> int:
    _ensure_metrics_loaded()
    with _METRICS_LOCK:
        return _COUNTERS.get(name, 0)


def histogram_snapshot(name: str) -> dict[str, object]:
    _ensure_metrics_loaded()
    with _METRICS_LOCK:
        state = _HISTOGRAMS.get(name)
        if state is None:
            return {}
        return state.snapshot()


def write_crash_log(
    error: BaseException,
    *,
    crash_dir: Path | None = None,
    context: str = "Unhandled exception",
    details: Mapping[str, object] | None = None,
) -> Path:
    target_dir = resolve_crash_dir(crash_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    occurred_at = datetime.now(UTC)
    timestamp = occurred_at.strftime("%Y%m%dT%H%M%S.%fZ")
    crash_path = _next_crash_path(target_dir, timestamp)
    metrics = snapshot_metrics()
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
        "metrics_path": resolve_metrics_path(),
        "metrics_persistence_enabled": metrics_persistence_enabled(),
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


def report_crash(
    error: BaseException,
    *,
    context: str = "Unhandled exception",
    details: Mapping[str, object] | None = None,
    stream: IO[str] | None = None,
) -> Path | None:
    target_stream = stream or sys.stderr
    try:
        crash_path = write_crash_log(error, context=context, details=details)
    except Exception as write_error:
        increment_counter("crash_log_write_failures")
        increment_counter("crashes_reported")
        increment_counter(f"crashes.{type(error).__name__}")
        target_stream.write(
            "unhandled exception; failed to write crash log: "
            f"{type(write_error).__name__}: {write_error}\n"
        )
        return None
    increment_counter("crashes_reported")
    increment_counter(f"crashes.{type(error).__name__}")
    target_stream.write(f"unhandled exception; crash log written to {crash_path}\n")
    return crash_path


def install_crash_handlers(*, stream: IO[str] | None = None) -> None:
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


def _parse_log_policy_value(raw: str) -> str | int:
    value = raw.strip()
    if value.isdigit():
        return int(value)
    return value


def _ensure_metrics_loaded() -> None:
    global _METRICS_LOADED
    path = resolve_metrics_path()
    with _METRICS_LOCK:
        if _METRICS_LOADED:
            return
        _METRICS_LOADED = True
        if path is None or not path.exists():
            return
        persisted = load_metrics_state(path)
        _COUNTERS.update(persisted.counters)
        _HISTOGRAMS.update(
            {
                name: _HistogramState.from_snapshot(snapshot)
                for name, snapshot in persisted.histograms.items()
            }
        )
        _RECENT_SNAPSHOTS.extend(cast(list[SnapshotRecord], persisted.recent_snapshots))


def _persist_metrics_unlocked() -> None:
    path = resolve_metrics_path()
    if path is None:
        return
    save_metrics_state(
        path,
        counters=dict(sorted(_COUNTERS.items())),
        histograms={name: state.snapshot() for name, state in sorted(_HISTOGRAMS.items())},
        recent_snapshots=cast(list[dict[str, object]], list(_RECENT_SNAPSHOTS)),
    )


def _rss_bytes() -> int | None:
    if resource is None:
        return None
    usage = resource.getrusage(resource.RUSAGE_SELF)
    rss = int(usage.ru_maxrss)
    if rss <= 0:
        return None
    if sys.platform == "darwin":
        return rss
    return rss * 1024


def _open_fd_count() -> int | None:
    for candidate in ("/proc/self/fd", "/dev/fd"):
        try:
            return len(os.listdir(candidate))
        except OSError:
            continue
    return None
