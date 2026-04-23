from __future__ import annotations

import os
import sys
import traceback
from dataclasses import dataclass, field
from collections.abc import Mapping
from datetime import UTC, datetime
from json import dumps as json_dumps
from json import loads as json_loads
from pathlib import Path
from threading import Lock
from typing import Any, TypedDict

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

    def to_json(self) -> dict[str, object]:
        return {
            "buckets_ms": list(self.buckets_ms),
            "count": self.count,
            "sum_ms": self.sum_ms,
            "min_ms": self.min_ms,
            "max_ms": self.max_ms,
            "bucket_hits": dict(sorted(self.bucket_hits.items())),
        }

    @classmethod
    def from_json(cls, payload: dict[str, object]) -> _HistogramState | None:
        buckets_payload = payload.get("buckets_ms")
        if not isinstance(buckets_payload, list) or not buckets_payload:
            return None
        buckets_ms = tuple(value for value in buckets_payload if isinstance(value, (int, float)))
        if len(buckets_ms) != len(buckets_payload):
            return None
        bucket_hits_payload = payload.get("bucket_hits")
        if not isinstance(bucket_hits_payload, dict):
            return None
        bucket_hits = {
            key: value
            for key, value in bucket_hits_payload.items()
            if isinstance(key, str) and isinstance(value, int)
        }
        if len(bucket_hits) != len(bucket_hits_payload):
            return None
        count = payload.get("count", 0)
        sum_ms = payload.get("sum_ms", 0.0)
        min_ms = payload.get("min_ms")
        max_ms = payload.get("max_ms")
        if not isinstance(count, int) or not isinstance(sum_ms, (int, float)):
            return None
        if min_ms is not None and not isinstance(min_ms, (int, float)):
            return None
        if max_ms is not None and not isinstance(max_ms, (int, float)):
            return None
        return cls(
            buckets_ms=tuple(float(value) for value in buckets_ms),
            count=count,
            sum_ms=float(sum_ms),
            min_ms=float(min_ms) if isinstance(min_ms, (int, float)) else None,
            max_ms=float(max_ms) if isinstance(max_ms, (int, float)) else None,
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
    override_path = os.environ.get("EODINGA_METRICS_PATH")
    if override_path:
        return Path(override_path).expanduser()
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
    with _METRICS_LOCK:
        _load_metrics_locked()
        _COUNTERS[name] = _COUNTERS.get(name, 0) + value
        _persist_metrics_locked()
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
        _load_metrics_locked()
        state = _HISTOGRAMS.get(name)
        if state is None:
            state = _HistogramState(buckets_ms=buckets_ms)
            _HISTOGRAMS[name] = state
        state.observe(value_ms)
        _persist_metrics_locked()
    logger.bind(metric=name, **fields).debug("histogram {value_ms:.3f}ms", value_ms=value_ms)


def snapshot_metrics() -> MetricsSnapshot:
    with _METRICS_LOCK:
        _load_metrics_locked()
        counters = dict(sorted(_COUNTERS.items()))
        histograms: dict[str, dict[str, object]] = {
            name: state.snapshot() for name, state in sorted(_HISTOGRAMS.items())
        }
    return {"counters": counters, "histograms": histograms}


def reset_metrics() -> None:
    global _METRICS_LOADED
    with _METRICS_LOCK:
        _COUNTERS.clear()
        _HISTOGRAMS.clear()
        _METRICS_LOADED = True
        _persist_metrics_locked()


def record_snapshot(name: str, payload: Mapping[str, object]) -> None:
    logger.bind(metric=name, payload=dict(payload)).debug("snapshot recorded")


def counter_value(name: str) -> int:
    with _METRICS_LOCK:
        _load_metrics_locked()
        return _COUNTERS.get(name, 0)


def histogram_snapshot(name: str) -> dict[str, object]:
    with _METRICS_LOCK:
        _load_metrics_locked()
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
    return crash_path


def _format_detail_value(value: object) -> str:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return str(value)
    return json_dumps(value, sort_keys=True)


def _load_metrics_locked() -> None:
    global _METRICS_LOADED
    if _METRICS_LOADED:
        return
    _COUNTERS.clear()
    _HISTOGRAMS.clear()
    metrics_path = default_metrics_path()
    try:
        payload = json_loads(metrics_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        _METRICS_LOADED = True
        return
    except (OSError, ValueError, TypeError):
        _METRICS_LOADED = True
        return

    for name, value in _coerce_counter_payload(payload.get("counters", {})).items():
        _COUNTERS[name] = value
    for name, raw_histogram in _coerce_histogram_payload(payload.get("histograms", {})).items():
        _HISTOGRAMS[name] = raw_histogram
    _METRICS_LOADED = True


def _persist_metrics_locked() -> None:
    metrics_path = default_metrics_path()
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "counters": dict(sorted(_COUNTERS.items())),
        "histograms": {
            name: state.to_json() for name, state in sorted(_HISTOGRAMS.items())
        },
    }
    temp_path = metrics_path.with_suffix(f"{metrics_path.suffix}.tmp")
    temp_path.write_text(json_dumps(payload, sort_keys=True), encoding="utf-8")
    temp_path.replace(metrics_path)


def _coerce_counter_payload(payload: object) -> dict[str, int]:
    if not isinstance(payload, dict):
        return {}
    counters: dict[str, int] = {}
    for key, value in payload.items():
        if isinstance(key, str) and isinstance(value, int):
            counters[key] = value
    return counters


def _coerce_histogram_payload(payload: object) -> dict[str, _HistogramState]:
    if not isinstance(payload, dict):
        return {}
    histograms: dict[str, _HistogramState] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        state = _HistogramState.from_json(value)
        if state is not None:
            histograms[key] = state
    return histograms
