from __future__ import annotations

import os
import sys
import tempfile
import threading
import traceback
from contextlib import contextmanager
from dataclasses import dataclass, field
from collections.abc import Mapping
from datetime import UTC, datetime
from json import dumps as json_dumps
from json import loads as json_loads
from pathlib import Path
from threading import Lock
from time import monotonic, sleep, time
from typing import IO, Any, Callable, TypedDict

from loguru import logger

_DEFAULT_HISTOGRAM_BUCKETS_MS = (1.0, 5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0)
_METRICS_LOCK = Lock()
_COUNTERS: dict[str, int] = {}
_HISTOGRAMS: dict[str, _HistogramState] = {}
_PROCESS_STARTED_AT = datetime.now(UTC)


class MetricsSnapshot(TypedDict):
    counters: dict[str, int]
    histograms: dict[str, dict[str, object]]
    generated_at: str
    uptime_ms: float


class _PersistedHistogram(TypedDict):
    buckets_ms: list[float]
    count: int
    sum_ms: float
    min_ms: float | None
    max_ms: float | None
    bucket_hits: dict[str, int]


class _PersistedMetrics(TypedDict):
    counters: dict[str, int]
    histograms: dict[str, _PersistedHistogram]


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


def default_crash_dir() -> Path:
    if sys.platform == "darwin":
        return default_logs_dir() / "crashes"
    return default_state_dir() / "crashes"


def file_logging_enabled() -> bool:
    return os.environ.get("EODINGA_DISABLE_FILE_LOGGING") != "1"


def resolve_metrics_path(metrics_path: Path | None = None) -> Path | None:
    if os.environ.get("EODINGA_DISABLE_METRICS_PERSISTENCE") == "1":
        return None
    if metrics_path is not None:
        return metrics_path.expanduser()
    override_path = os.environ.get("EODINGA_METRICS_PATH")
    if override_path:
        return Path(override_path).expanduser()
    if "PYTEST_CURRENT_TEST" in os.environ:
        return None
    return default_state_dir() / "metrics.json"


def metrics_persistence_enabled() -> bool:
    return resolve_metrics_path() is not None


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
    def _mutate() -> None:
        _COUNTERS[name] = _COUNTERS.get(name, 0) + value

    _mutate_metrics(_mutate)
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
    def _mutate() -> None:
        state = _HISTOGRAMS.get(name)
        if state is None:
            state = _HistogramState(buckets_ms=buckets_ms)
            _HISTOGRAMS[name] = state
        state.observe(value_ms)

    _mutate_metrics(_mutate)
    logger.bind(metric=name, **fields).debug("histogram {value_ms:.3f}ms", value_ms=value_ms)


def snapshot_metrics() -> MetricsSnapshot:
    with _METRICS_LOCK:
        _refresh_metrics_from_disk_unlocked()
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
        _clear_metrics_unlocked()
        _persist_metrics_unlocked()


def record_snapshot(name: str, payload: Mapping[str, object]) -> None:
    logger.bind(metric=name, payload=dict(payload)).debug("snapshot recorded")


def counter_value(name: str) -> int:
    with _METRICS_LOCK:
        _refresh_metrics_from_disk_unlocked()
        return _COUNTERS.get(name, 0)


def histogram_snapshot(name: str) -> dict[str, object]:
    with _METRICS_LOCK:
        _refresh_metrics_from_disk_unlocked()
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


def _mutate_metrics(mutator: Callable[[], None]) -> None:
    with _METRICS_LOCK:
        path = resolve_metrics_path()
        if path is None:
            mutator()
            return
        try:
            with _metrics_path_lock(path):
                _load_metrics_from_disk_unlocked(path)
                mutator()
                _write_metrics_to_disk_unlocked(path)
        except OSError:
            mutator()


def _persist_metrics_unlocked() -> None:
    path = resolve_metrics_path()
    if path is None:
        return
    try:
        with _metrics_path_lock(path):
            _write_metrics_to_disk_unlocked(path)
    except OSError:
        return


def _refresh_metrics_from_disk_unlocked() -> None:
    path = resolve_metrics_path()
    if path is None:
        return
    try:
        with _metrics_path_lock(path):
            _load_metrics_from_disk_unlocked(path)
    except OSError:
        return


def _clear_metrics_unlocked() -> None:
    _COUNTERS.clear()
    _HISTOGRAMS.clear()


def _load_metrics_from_disk_unlocked(path: Path) -> None:
    payload = _read_metrics_file(path)
    _clear_metrics_unlocked()
    _COUNTERS.update(payload["counters"])
    for name, histogram in payload["histograms"].items():
        _HISTOGRAMS[name] = _deserialize_histogram(histogram)


def _write_metrics_to_disk_unlocked(path: Path) -> None:
    payload: _PersistedMetrics = {
        "counters": dict(sorted(_COUNTERS.items())),
        "histograms": {
            name: _serialize_histogram(state) for name, state in sorted(_HISTOGRAMS.items())
        },
    }
    _atomic_write_text(path, json_dumps(payload, sort_keys=True))


def _read_metrics_file(path: Path) -> _PersistedMetrics:
    if not path.exists():
        return {"counters": {}, "histograms": {}}
    raw = json_loads(path.read_text(encoding="utf-8"))
    counters_raw = raw.get("counters", {})
    histograms_raw = raw.get("histograms", {})
    counters = {str(name): int(value) for name, value in counters_raw.items()}
    histograms: dict[str, _PersistedHistogram] = {}
    for name, payload in histograms_raw.items():
        if not isinstance(payload, dict):
            continue
        histograms[str(name)] = {
            "buckets_ms": [float(bucket) for bucket in payload.get("buckets_ms", [])],
            "count": int(payload.get("count", 0)),
            "sum_ms": float(payload.get("sum_ms", 0.0)),
            "min_ms": float(payload["min_ms"]) if payload.get("min_ms") is not None else None,
            "max_ms": float(payload["max_ms"]) if payload.get("max_ms") is not None else None,
            "bucket_hits": {
                str(label): int(count) for label, count in payload.get("bucket_hits", {}).items()
            },
        }
    return {"counters": counters, "histograms": histograms}


def _serialize_histogram(state: _HistogramState) -> _PersistedHistogram:
    return {
        "buckets_ms": [float(bucket) for bucket in state.buckets_ms],
        "count": state.count,
        "sum_ms": state.sum_ms,
        "min_ms": state.min_ms,
        "max_ms": state.max_ms,
        "bucket_hits": dict(sorted(state.bucket_hits.items())),
    }


def _deserialize_histogram(payload: _PersistedHistogram) -> _HistogramState:
    return _HistogramState(
        buckets_ms=tuple(payload["buckets_ms"]) or _DEFAULT_HISTOGRAM_BUCKETS_MS,
        count=payload["count"],
        sum_ms=payload["sum_ms"],
        min_ms=payload["min_ms"],
        max_ms=payload["max_ms"],
        bucket_hits=dict(payload["bucket_hits"]),
    )


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


@contextmanager
def _metrics_path_lock(path: Path, *, timeout_s: float = 2.0):
    lock_path = path.with_name(f"{path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    started = monotonic()
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            break
        except FileExistsError:
            try:
                if time() - lock_path.stat().st_mtime > timeout_s:
                    lock_path.unlink()
                    continue
            except FileNotFoundError:
                continue
            if monotonic() - started >= timeout_s:
                raise TimeoutError(f"timed out acquiring metrics lock for {path}")
            sleep(0.01)
    try:
        yield
    finally:
        os.close(fd)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass
