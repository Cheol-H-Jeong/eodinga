from __future__ import annotations

import os
import sys
import tempfile
import threading
import traceback
from dataclasses import dataclass, field
from collections.abc import Mapping
from datetime import UTC, datetime
from json import dumps as json_dumps, loads as json_loads
from pathlib import Path
from threading import Lock
from typing import IO, Any, TypedDict

from loguru import logger

_DEFAULT_HISTOGRAM_BUCKETS_MS = (1.0, 5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0)
_METRICS_LOCK = Lock()
_COUNTERS: dict[str, int] = {}
_HISTOGRAMS: dict[str, _HistogramState] = {}
_PROCESS_STARTED_AT = datetime.now(UTC)
_METRICS_SCHEMA_VERSION = 1


class MetricsSnapshot(TypedDict):
    counters: dict[str, int]
    histograms: dict[str, dict[str, object]]
    generated_at: str
    uptime_ms: float


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


def default_metrics_path() -> Path:
    return default_state_dir() / "metrics.json"


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


def resolve_crash_dir(crash_dir: Path | None = None) -> Path:
    if crash_dir is not None:
        return crash_dir.expanduser()
    override_dir = os.environ.get("EODINGA_CRASH_DIR")
    if override_dir:
        return Path(override_dir).expanduser()
    return default_crash_dir()


def resolve_metrics_path(metrics_path: Path | None = None) -> Path | None:
    if metrics_path is not None:
        return metrics_path.expanduser()
    override_path = os.environ.get("EODINGA_METRICS_PATH")
    if override_path:
        return Path(override_path).expanduser()
    if "PYTEST_CURRENT_TEST" in os.environ:
        return None
    return default_metrics_path()


def configure_logging(level: str = "INFO", log_path: Path | None = None) -> None:
    logger.remove()
    logger.add(sys.stderr, level=level.upper())
    target = resolve_log_path(log_path)
    if target is None:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    logger.add(target, rotation="5 MB", retention=5, level=level.upper())


def get_logger(name: str | None = None) -> Any:
    return logger.bind(component=name or "eodinga")


def increment_counter(name: str, value: int = 1, **fields: object) -> None:
    with _METRICS_LOCK:
        _COUNTERS[name] = _COUNTERS.get(name, 0) + value
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
        state = _HISTOGRAMS.get(name)
        if state is None:
            state = _HistogramState(buckets_ms=buckets_ms)
            _HISTOGRAMS[name] = state
        state.observe(value_ms)
    logger.bind(metric=name, **fields).debug("histogram {value_ms:.3f}ms", value_ms=value_ms)


def snapshot_metrics() -> MetricsSnapshot:
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
        "uptime_ms": round((now - _PROCESS_STARTED_AT).total_seconds() * 1000, 3),
    }


def reset_metrics() -> None:
    with _METRICS_LOCK:
        _COUNTERS.clear()
        _HISTOGRAMS.clear()


def flush_metrics(metrics_path: Path | None = None) -> Path | None:
    target = resolve_metrics_path(metrics_path)
    if target is None:
        return None
    payload = _serialize_metrics()
    _atomic_write_text(target, json_dumps(payload, sort_keys=True))
    return target


def load_metrics(metrics_path: Path | None = None) -> Path | None:
    target = resolve_metrics_path(metrics_path)
    if target is None or not target.exists():
        return target
    try:
        raw = json_loads(target.read_text(encoding="utf-8"))
    except ValueError:
        logger.warning("failed to parse metrics snapshot {}", target)
        return target
    counters = _coerce_counters(raw.get("counters"))
    histograms = _coerce_histograms(raw.get("histograms"))
    process_started_at = _coerce_process_started_at(raw.get("process_started_at"))
    with _METRICS_LOCK:
        _COUNTERS.clear()
        _COUNTERS.update(counters)
        _HISTOGRAMS.clear()
        _HISTOGRAMS.update(histograms)
    global _PROCESS_STARTED_AT
    _PROCESS_STARTED_AT = process_started_at
    return target


def record_snapshot(name: str, payload: Mapping[str, object]) -> None:
    logger.bind(metric=name, payload=dict(payload)).debug("snapshot recorded")


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
    from eodinga import __version__

    target_dir = resolve_crash_dir(crash_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    occurred_at = datetime.now(UTC)
    timestamp = occurred_at.strftime("%Y%m%dT%H%M%S.%fZ")
    crash_path = _next_crash_path(target_dir, timestamp)
    metadata: dict[str, object] = {
        "timestamp": timestamp,
        "pid": os.getpid(),
        "version": __version__,
        "platform": sys.platform,
        "python": sys.version.split()[0],
        "cwd": str(Path.cwd()),
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
) -> Path:
    crash_path = write_crash_log(error, context=context, details=details)
    increment_counter("crashes_reported")
    target_stream = stream or sys.stderr
    target_stream.write(f"unhandled exception; crash log written to {crash_path}\n")
    return crash_path


def install_crash_handlers(*, stream: IO[str] | None = None) -> None:
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


def _serialize_metrics() -> dict[str, object]:
    snapshot = snapshot_metrics()
    return {
        "schema_version": _METRICS_SCHEMA_VERSION,
        "process_started_at": _PROCESS_STARTED_AT.isoformat().replace("+00:00", "Z"),
        "generated_at": snapshot["generated_at"],
        "uptime_ms": snapshot["uptime_ms"],
        "counters": snapshot["counters"],
        "histograms": snapshot["histograms"],
    }


def _coerce_counters(raw: object) -> dict[str, int]:
    if not isinstance(raw, dict):
        return {}
    counters: dict[str, int] = {}
    for key, value in raw.items():
        if isinstance(key, str) and isinstance(value, int):
            counters[key] = value
    return counters


def _coerce_histograms(raw: object) -> dict[str, _HistogramState]:
    if not isinstance(raw, dict):
        return {}
    histograms: dict[str, _HistogramState] = {}
    for name, payload in raw.items():
        if not isinstance(name, str) or not isinstance(payload, dict):
            continue
        state = _histogram_state_from_payload(payload)
        if state is not None:
            histograms[name] = state
    return histograms


def _histogram_state_from_payload(payload: dict[object, object]) -> _HistogramState | None:
    count = payload.get("count")
    sum_ms = payload.get("sum_ms")
    min_ms = payload.get("min_ms")
    max_ms = payload.get("max_ms")
    buckets = payload.get("buckets")
    if not isinstance(count, int) or not isinstance(sum_ms, (int, float)):
        return None
    bucket_hits: dict[str, int] = {}
    if isinstance(buckets, dict):
        for key, value in buckets.items():
            if isinstance(key, str) and isinstance(value, int):
                bucket_hits[key] = value
    return _HistogramState(
        buckets_ms=_DEFAULT_HISTOGRAM_BUCKETS_MS,
        count=count,
        sum_ms=float(sum_ms),
        min_ms=float(min_ms) if isinstance(min_ms, (int, float)) else None,
        max_ms=float(max_ms) if isinstance(max_ms, (int, float)) else None,
        bucket_hits=bucket_hits,
    )


def _coerce_process_started_at(raw: object) -> datetime:
    if not isinstance(raw, str):
        return datetime.now(UTC)
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return datetime.now(UTC)


def _atomic_write_text(path: Path, contents: str) -> None:
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=directory,
        text=True,
    )
    temp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        _fsync_directory(directory)
    except Exception:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass
        raise


def _fsync_directory(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)
