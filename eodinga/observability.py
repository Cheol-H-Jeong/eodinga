from __future__ import annotations

import json
import os
import sys
import traceback
from dataclasses import dataclass, field
from collections.abc import Mapping
from datetime import UTC, datetime
from json import dumps as json_dumps
from pathlib import Path
from threading import Lock
from typing import Any, Callable, TypedDict

from loguru import logger

_DEFAULT_HISTOGRAM_BUCKETS_MS = (1.0, 5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0)
_METRICS_LOCK = Lock()
_COUNTERS: dict[str, int] = {}
_HISTOGRAMS: dict[str, _HistogramState] = {}
_METRICS_LOADED = False


class MetricsSnapshot(TypedDict):
    counters: dict[str, int]
    histograms: dict[str, dict[str, object]]


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

    @classmethod
    def from_snapshot(
        cls,
        snapshot: Mapping[str, object],
        *,
        buckets_ms: tuple[float, ...] = _DEFAULT_HISTOGRAM_BUCKETS_MS,
    ) -> _HistogramState:
        bucket_payload = snapshot.get("buckets", {})
        bucket_hits = (
            {str(name): _coerce_int(value) for name, value in bucket_payload.items()}
            if isinstance(bucket_payload, Mapping)
            else {}
        )
        min_ms = snapshot.get("min_ms")
        max_ms = snapshot.get("max_ms")
        return cls(
            buckets_ms=buckets_ms,
            count=_coerce_int(snapshot.get("count", 0)),
            sum_ms=_coerce_float(snapshot.get("sum_ms", 0.0)),
            min_ms=_coerce_float(min_ms) if min_ms is not None else None,
            max_ms=_coerce_float(max_ms) if max_ms is not None else None,
            bucket_hits=bucket_hits,
        )


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


def configure_logging(level: str = "INFO", log_path: Path | None = None) -> None:
    logger.remove()
    logger.add(sys.stderr, level=level.upper())
    if os.environ.get("EODINGA_DISABLE_FILE_LOGGING") == "1":
        return
    effective_log_path = log_path
    if effective_log_path is None:
        override_path = os.environ.get("EODINGA_LOG_PATH")
        if override_path:
            effective_log_path = Path(override_path)
        else:
            if "PYTEST_CURRENT_TEST" in os.environ:
                return
            effective_log_path = default_log_path()
    target = effective_log_path.expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    logger.add(target, rotation="5 MB", retention=5, level=level.upper())


def get_logger(name: str | None = None) -> Any:
    return logger.bind(component=name or "eodinga")


def increment_counter(name: str, value: int = 1, **fields: object) -> None:
    _mutate_metrics(lambda counters, _histograms: counters.__setitem__(name, counters.get(name, 0) + value))
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
    def mutate(_counters: dict[str, int], histograms: dict[str, _HistogramState]) -> None:
        state = histograms.get(name)
        if state is None:
            state = _HistogramState(buckets_ms=buckets_ms)
            histograms[name] = state
        state.observe(value_ms)

    _mutate_metrics(mutate)
    logger.bind(metric=name, **fields).debug("histogram {value_ms:.3f}ms", value_ms=value_ms)


def snapshot_metrics() -> MetricsSnapshot:
    _ensure_metrics_loaded()
    return _snapshot_metrics_unlocked()


def reset_metrics() -> None:
    metrics_path = _resolve_metrics_path()
    if metrics_path is not None:
        with _locked_metrics_file(metrics_path):
            _clear_metrics_state()
            if metrics_path.exists():
                metrics_path.unlink()
        return
    _clear_metrics_state()


def _clear_metrics_state() -> None:
    global _METRICS_LOADED
    with _METRICS_LOCK:
        _COUNTERS.clear()
        _HISTOGRAMS.clear()
        _METRICS_LOADED = True


def record_snapshot(name: str, payload: Mapping[str, object]) -> None:
    logger.bind(metric=name, payload=dict(payload)).debug("snapshot recorded")


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
    from eodinga import __version__

    override_dir = os.environ.get("EODINGA_CRASH_DIR")
    target_dir = (crash_dir or (Path(override_dir) if override_dir else default_crash_dir())).expanduser()
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    crash_path = target_dir / f"crash-{timestamp}.log"
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
    increment_counter("crashes_written")
    increment_counter(f"crashes.{type(error).__name__}")
    return crash_path


def latest_crash_log_path(crash_dir: Path | None = None) -> Path | None:
    override_dir = os.environ.get("EODINGA_CRASH_DIR")
    target_dir = (crash_dir or (Path(override_dir) if override_dir else default_crash_dir())).expanduser()
    if not target_dir.exists():
        return None
    candidates = sorted(target_dir.glob("crash-*.log"))
    if not candidates:
        return None
    return candidates[-1]


def _format_detail_value(value: object) -> str:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return str(value)
    return json_dumps(value, sort_keys=True)


def _coerce_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        return int(value)
    return 0


def _coerce_float(value: object) -> float:
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(value)
    return 0.0


def _resolve_metrics_path() -> Path | None:
    override_path = os.environ.get("EODINGA_METRICS_PATH")
    if override_path:
        return Path(override_path)
    if os.environ.get("EODINGA_DISABLE_METRICS_PERSISTENCE") == "1":
        return None
    if "PYTEST_CURRENT_TEST" in os.environ:
        return None
    return default_metrics_path()


def _ensure_metrics_loaded() -> None:
    global _METRICS_LOADED
    metrics_path = _resolve_metrics_path()
    with _METRICS_LOCK:
        if _METRICS_LOADED:
            return
    if metrics_path is None:
        with _METRICS_LOCK:
            _METRICS_LOADED = True
        return
    with _locked_metrics_file(metrics_path):
        counters, histograms = _read_metrics_from_disk(metrics_path)
        with _METRICS_LOCK:
            _COUNTERS.clear()
            _COUNTERS.update(counters)
            _HISTOGRAMS.clear()
            _HISTOGRAMS.update(histograms)
            _METRICS_LOADED = True


def _mutate_metrics(
    mutate: Callable[[dict[str, int], dict[str, _HistogramState]], None],
) -> None:
    global _METRICS_LOADED
    metrics_path = _resolve_metrics_path()
    if metrics_path is None:
        with _METRICS_LOCK:
            mutate(_COUNTERS, _HISTOGRAMS)
            _METRICS_LOADED = True
        return

    with _locked_metrics_file(metrics_path):
        counters, histograms = _read_metrics_from_disk(metrics_path)
        mutate(counters, histograms)
        _write_metrics_to_disk(metrics_path, counters, histograms)
        with _METRICS_LOCK:
            _COUNTERS.clear()
            _COUNTERS.update(counters)
            _HISTOGRAMS.clear()
            _HISTOGRAMS.update(histograms)
            _METRICS_LOADED = True


def _snapshot_metrics_unlocked() -> MetricsSnapshot:
    with _METRICS_LOCK:
        counters = dict(sorted(_COUNTERS.items()))
        histograms: dict[str, dict[str, object]] = {
            name: state.snapshot() for name, state in sorted(_HISTOGRAMS.items())
        }
    return {"counters": counters, "histograms": histograms}


def _read_metrics_from_disk(metrics_path: Path) -> tuple[dict[str, int], dict[str, _HistogramState]]:
    if not metrics_path.exists():
        return {}, {}
    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    counter_payload = payload.get("counters", {})
    counters = (
        {str(name): _coerce_int(value) for name, value in counter_payload.items()}
        if isinstance(counter_payload, Mapping)
        else {}
    )
    histogram_payload = payload.get("histograms", {})
    histograms = {
        str(name): _HistogramState.from_snapshot(value)
        for name, value in histogram_payload.items()
        if isinstance(histogram_payload, Mapping) and isinstance(value, Mapping)
    }
    return counters, histograms


def _write_metrics_to_disk(
    metrics_path: Path,
    counters: dict[str, int],
    histograms: dict[str, _HistogramState],
) -> None:
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "counters": dict(sorted(counters.items())),
        "histograms": {
            name: state.snapshot() for name, state in sorted(histograms.items())
        },
    }
    temp_path = metrics_path.parent / f".{metrics_path.name}.{os.getpid()}.tmp"
    try:
        temp_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        os.replace(temp_path, metrics_path)
    finally:
        temp_path.unlink(missing_ok=True)


class _MetricsFileLock:
    def __init__(self, metrics_path: Path) -> None:
        self._lock_path = metrics_path.parent / f".{metrics_path.name}.lock"
        self._handle: Any | None = None

    def __enter__(self) -> None:
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self._lock_path.open("a+b")
        if os.name == "nt":
            import msvcrt

            self._handle.seek(0)
            self._handle.write(b"0")
            self._handle.flush()
            self._handle.seek(0)
            msvcrt.locking(self._handle.fileno(), msvcrt.LK_LOCK, 1)
            return
        import fcntl

        fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX)

    def __exit__(self, *_args: object) -> None:
        if self._handle is None:
            return
        if os.name == "nt":
            import msvcrt

            self._handle.seek(0)
            msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        self._handle.close()
        self._handle = None


def _locked_metrics_file(metrics_path: Path) -> _MetricsFileLock:
    return _MetricsFileLock(metrics_path)
