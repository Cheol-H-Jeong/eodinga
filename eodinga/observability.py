from __future__ import annotations

import os
import sys
import threading
from collections import deque
from dataclasses import dataclass, field
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import IO, Any, TypedDict

from loguru import logger

from eodinga.observability_state import (
    PersistedHistogram,
    load_metrics_state,
    merge_metrics_state,
    write_metrics_state,
)

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
_COUNTER_DELTAS: dict[str, int] = {}
_HISTOGRAMS: dict[str, _HistogramState] = {}
_HISTOGRAM_DELTAS: dict[str, _HistogramState] = {}
_PROCESS_STARTED_AT = datetime.now(UTC)
_PERSISTED_AT: str | None = None
_PERSISTED_METRICS_LOADED = False


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
            "count": self.count,
            "sum_ms": round(self.sum_ms, 3),
            "min_ms": round(self.min_ms, 3) if self.min_ms is not None else 0.0,
            "max_ms": round(self.max_ms, 3) if self.max_ms is not None else 0.0,
            "buckets": dict(sorted(self.bucket_hits.items())),
        }


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
_SNAPSHOT_DELTAS: list[SnapshotRecord] = []


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
    from eodinga.crash_observability import default_crash_dir as _default_crash_dir

    return _default_crash_dir()


def default_metrics_path() -> Path:
    return default_state_dir() / "metrics" / "runtime-metrics.json"


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


def resolve_crash_dir(crash_dir: Path | None = None) -> Path:
    from eodinga.crash_observability import resolve_crash_dir as _resolve_crash_dir

    return _resolve_crash_dir(crash_dir)


def resolve_metrics_path(metrics_path: Path | None = None) -> Path | None:
    if metrics_path is not None:
        return metrics_path.expanduser()
    override_path = os.environ.get("EODINGA_METRICS_PATH")
    if override_path:
        return Path(override_path).expanduser()
    if "PYTEST_CURRENT_TEST" in os.environ:
        return None
    return default_metrics_path()


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
    with _METRICS_LOCK:
        _COUNTERS[name] = _COUNTERS.get(name, 0) + value
        _COUNTER_DELTAS[name] = _COUNTER_DELTAS.get(name, 0) + value
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
    with _METRICS_LOCK:
        _observe_histogram(_HISTOGRAMS, name, value_ms, buckets_ms=buckets_ms)
        _observe_histogram(_HISTOGRAM_DELTAS, name, value_ms, buckets_ms=buckets_ms)
    logger.bind(metric=name, **fields).debug("histogram {value_ms:.3f}ms", value_ms=value_ms)


def snapshot_metrics() -> MetricsSnapshot:
    from eodinga import __version__

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
    global _PERSISTED_AT, _PERSISTED_METRICS_LOADED
    with _METRICS_LOCK:
        _COUNTERS.clear()
        _COUNTER_DELTAS.clear()
        _HISTOGRAMS.clear()
        _HISTOGRAM_DELTAS.clear()
        _RECENT_SNAPSHOTS.clear()
        _SNAPSHOT_DELTAS.clear()
    _PERSISTED_AT = None
    _PERSISTED_METRICS_LOADED = False


def record_snapshot(name: str, payload: Mapping[str, object]) -> None:
    record: SnapshotRecord = {
        "name": name,
        "recorded_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "payload": dict(payload),
    }
    with _METRICS_LOCK:
        _RECENT_SNAPSHOTS.append(record)
        _SNAPSHOT_DELTAS.append(record)
    logger.bind(metric=name, payload=record["payload"]).debug("snapshot recorded")


def load_persisted_metrics(metrics_path: Path | None = None) -> Path | None:
    global _PERSISTED_AT, _PERSISTED_METRICS_LOADED
    target = resolve_metrics_path(metrics_path)
    if target is None or _PERSISTED_METRICS_LOADED:
        return target
    state = load_metrics_state(target)
    with _METRICS_LOCK:
        _COUNTERS.clear()
        _COUNTERS.update(state["counters"])
        _COUNTER_DELTAS.clear()
        _HISTOGRAMS.clear()
        _HISTOGRAMS.update(
            {
                name: _histogram_state_from_persisted(histogram)
                for name, histogram in state["histograms"].items()
            }
        )
        _HISTOGRAM_DELTAS.clear()
        _RECENT_SNAPSHOTS.clear()
        _RECENT_SNAPSHOTS.extend(_snapshot_records(state["recent_snapshots"]))
        _SNAPSHOT_DELTAS.clear()
    _PERSISTED_AT = state["persisted_at"] or None
    _PERSISTED_METRICS_LOADED = True
    return target


def flush_metrics(metrics_path: Path | None = None) -> Path | None:
    global _PERSISTED_AT, _PERSISTED_METRICS_LOADED
    target = resolve_metrics_path(metrics_path)
    if target is None:
        return None
    with _METRICS_LOCK:
        if not _COUNTER_DELTAS and not _HISTOGRAM_DELTAS and not _SNAPSHOT_DELTAS:
            _PERSISTED_METRICS_LOADED = True
            return target
        merged = merge_metrics_state(
            load_metrics_state(target),
            delta_counters=dict(_COUNTER_DELTAS),
            delta_histograms={
                name: _persisted_histogram(state) for name, state in _HISTOGRAM_DELTAS.items()
            },
            delta_snapshots=[dict(snapshot) for snapshot in _SNAPSHOT_DELTAS],
            snapshot_limit=_RECENT_SNAPSHOT_LIMIT,
        )
        write_metrics_state(target, merged)
        _COUNTERS.clear()
        _COUNTERS.update(merged["counters"])
        _COUNTER_DELTAS.clear()
        _HISTOGRAMS.clear()
        _HISTOGRAMS.update(
            {
                name: _histogram_state_from_persisted(histogram)
                for name, histogram in merged["histograms"].items()
            }
        )
        _HISTOGRAM_DELTAS.clear()
        _RECENT_SNAPSHOTS.clear()
        _RECENT_SNAPSHOTS.extend(_snapshot_records(merged["recent_snapshots"]))
        _SNAPSHOT_DELTAS.clear()
    _PERSISTED_AT = merged["persisted_at"]
    _PERSISTED_METRICS_LOADED = True
    return target


def recent_snapshots() -> list[SnapshotRecord]:
    with _METRICS_LOCK:
        return list(_RECENT_SNAPSHOTS)


def counter_value(name: str) -> int:
    with _METRICS_LOCK:
        return _COUNTERS.get(name, 0)


def histogram_snapshot(name: str) -> dict[str, object]:
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
    from eodinga.crash_observability import write_crash_log as _write_crash_log

    return _write_crash_log(error, crash_dir=crash_dir, context=context, details=details)


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
    from eodinga.crash_observability import install_crash_handlers as _install_crash_handlers

    _install_crash_handlers(stream=stream)


def _observe_histogram(
    target: dict[str, _HistogramState],
    name: str,
    value_ms: float,
    *,
    buckets_ms: tuple[float, ...],
) -> None:
    state = target.get(name)
    if state is None:
        state = _HistogramState(buckets_ms=buckets_ms)
        target[name] = state
    state.observe(value_ms)


def _persisted_histogram(state: _HistogramState) -> PersistedHistogram:
    return {
        "bucket_hits": dict(sorted(state.bucket_hits.items())),
        "buckets_ms": list(state.buckets_ms),
        "count": state.count,
        "sum_ms": state.sum_ms,
        "min_ms": state.min_ms,
        "max_ms": state.max_ms,
    }


def _histogram_state_from_persisted(histogram: PersistedHistogram) -> _HistogramState:
    return _HistogramState(
        buckets_ms=tuple(histogram["buckets_ms"]) or _DEFAULT_HISTOGRAM_BUCKETS_MS,
        count=histogram["count"],
        sum_ms=histogram["sum_ms"],
        min_ms=histogram["min_ms"],
        max_ms=histogram["max_ms"],
        bucket_hits=dict(histogram["bucket_hits"]),
    )


def _snapshot_records(records: list[dict[str, object]]) -> list[SnapshotRecord]:
    snapshots: list[SnapshotRecord] = []
    for record in records:
        payload = record.get("payload")
        snapshots.append(
            SnapshotRecord(
                name=str(record.get("name", "")),
                recorded_at=str(record.get("recorded_at", "")),
                payload=dict(payload) if isinstance(payload, dict) else {},
            )
        )
    return snapshots


def _parse_log_policy_value(raw: str) -> str | int:
    value = raw.strip()
    if value.isdigit():
        return int(value)
    return value


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
