from __future__ import annotations

import os
import json
import sys
import traceback
from dataclasses import dataclass, field
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any

from loguru import logger

_DEFAULT_HISTOGRAM_BUCKETS_MS = (1.0, 5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0)
_METRICS_LOCK = Lock()
_COUNTERS: dict[str, int] = {}
_HISTOGRAMS: dict[str, _HistogramState] = {}
_ACTIVE_LOG_PATH: Path | None = None


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
    xdg_state = os.environ.get("XDG_STATE_HOME")
    if xdg_state:
        return Path(xdg_state) / "eodinga"
    return Path.home() / ".local" / "state" / "eodinga"


def default_logs_dir() -> Path:
    return default_state_dir() / "logs"


def default_log_path() -> Path:
    return default_logs_dir() / "eodinga.log"


def default_crash_dir() -> Path:
    return default_state_dir() / "crashes"


def resolved_log_path(log_path: Path | None = None) -> Path | None:
    if os.environ.get("EODINGA_DISABLE_FILE_LOGGING") == "1":
        return None
    if log_path is not None:
        return log_path.expanduser()
    override_path = os.environ.get("EODINGA_LOG_PATH")
    if override_path:
        return Path(override_path).expanduser()
    if "PYTEST_CURRENT_TEST" in os.environ:
        return None
    return default_log_path()


def resolved_crash_dir(crash_dir: Path | None = None) -> Path:
    override_dir = os.environ.get("EODINGA_CRASH_DIR")
    if crash_dir is not None:
        return crash_dir.expanduser()
    if override_dir:
        return Path(override_dir).expanduser()
    return default_crash_dir()


def configure_logging(level: str = "INFO", log_path: Path | None = None) -> None:
    global _ACTIVE_LOG_PATH
    logger.remove()
    logger.add(sys.stderr, level=level.upper())
    target = resolved_log_path(log_path)
    _ACTIVE_LOG_PATH = target
    if target is None:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    logger.add(
        target,
        rotation="5 MB",
        retention=5,
        encoding="utf-8",
        level=level.upper(),
    )


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


def snapshot_metrics() -> dict[str, object]:
    with _METRICS_LOCK:
        counters = dict(sorted(_COUNTERS.items()))
        histograms = {name: state.snapshot() for name, state in sorted(_HISTOGRAMS.items())}
    return {"counters": counters, "histograms": histograms}


def reset_metrics() -> None:
    with _METRICS_LOCK:
        _COUNTERS.clear()
        _HISTOGRAMS.clear()


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


def active_log_path() -> Path | None:
    return _ACTIVE_LOG_PATH


def write_crash_log(
    error: BaseException,
    *,
    crash_dir: Path | None = None,
    context: str = "Unhandled exception",
) -> Path:
    target_dir = resolved_crash_dir(crash_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    crash_path = target_dir / f"crash-{timestamp}.log"
    lines = [
        f"{context}\n",
        f"timestamp={timestamp}\n",
        f"pid={os.getpid()}\n",
        f"log_path={active_log_path() or resolved_log_path()}\n",
        f"crash_dir={target_dir}\n",
        f"metrics={json.dumps(snapshot_metrics(), sort_keys=True)}\n",
        f"{type(error).__name__}: {error}\n",
        "\n",
        *traceback.format_exception(type(error), error, error.__traceback__),
    ]
    crash_path.write_text("".join(lines), encoding="utf-8")
    increment_counter("crashes_written")
    return crash_path
