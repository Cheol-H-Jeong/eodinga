from __future__ import annotations

import os
import platform
import sys
import traceback
from dataclasses import dataclass, field
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any, TypedDict

from eodinga import __version__
from loguru import logger

_DEFAULT_HISTOGRAM_BUCKETS_MS = (1.0, 5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0)
_METRICS_LOCK = Lock()
_COUNTERS: dict[str, int] = {}
_HISTOGRAMS: dict[str, _HistogramState] = {}


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


@dataclass(frozen=True)
class FileLogConfig:
    path: Path
    rotation: str = "5 MB"
    retention: int | str = 5
    compression: str | None = None
    serialize: bool = False


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


def runtime_metadata() -> dict[str, object]:
    return {
        "version": __version__,
        "platform": sys.platform,
        "python": platform.python_version(),
        "cwd": str(Path.cwd()),
        "pid": os.getpid(),
    }


def resolve_file_log_config(log_path: Path | None = None) -> FileLogConfig | None:
    if os.environ.get("EODINGA_DISABLE_FILE_LOGGING") == "1":
        return None
    effective_log_path = log_path
    if effective_log_path is None:
        override_path = os.environ.get("EODINGA_LOG_PATH")
        if override_path:
            effective_log_path = Path(override_path)
        else:
            if "PYTEST_CURRENT_TEST" in os.environ:
                return None
            effective_log_path = default_log_path()
    rotation = os.environ.get("EODINGA_LOG_ROTATION", "5 MB")
    retention_text = os.environ.get("EODINGA_LOG_RETENTION", "5")
    retention: int | str
    retention = int(retention_text) if retention_text.isdigit() else retention_text
    compression = os.environ.get("EODINGA_LOG_COMPRESSION") or None
    serialize = os.environ.get("EODINGA_LOG_SERIALIZE") == "1"
    return FileLogConfig(
        path=effective_log_path.expanduser(),
        rotation=rotation,
        retention=retention,
        compression=compression,
        serialize=serialize,
    )


def configure_logging(level: str = "INFO", log_path: Path | None = None) -> None:
    logger.remove()
    logger.add(sys.stderr, level=level.upper())
    file_config = resolve_file_log_config(log_path)
    if file_config is None:
        return
    target = file_config.path
    target.parent.mkdir(parents=True, exist_ok=True)
    logger.add(
        target,
        rotation=file_config.rotation,
        retention=file_config.retention,
        compression=file_config.compression,
        serialize=file_config.serialize,
        enqueue=True,
        backtrace=False,
        diagnose=False,
        level=level.upper(),
    )
    logger.bind(log_path=str(target)).debug("file logging enabled")


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


def write_crash_log(
    error: BaseException,
    *,
    crash_dir: Path | None = None,
    context: str = "Unhandled exception",
    command: str | None = None,
    metadata: Mapping[str, object] | None = None,
) -> Path:
    override_dir = os.environ.get("EODINGA_CRASH_DIR")
    target_dir = (crash_dir or (Path(override_dir) if override_dir else default_crash_dir())).expanduser()
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    crash_path = target_dir / f"crash-{timestamp}.log"
    merged_metadata = runtime_metadata()
    if metadata:
        merged_metadata.update(metadata)
    metrics = snapshot_metrics()
    lines = [
        f"{context}\n",
        f"timestamp={timestamp}\n",
        f"{type(error).__name__}: {error}\n",
        "\n",
    ]
    if command:
        lines.append(f"command={command}\n")
    for key, value in merged_metadata.items():
        lines.append(f"{key}={value}\n")
    if metrics["counters"] or metrics["histograms"]:
        lines.extend(
            [
                "metrics.counters="
                f"{','.join(f'{name}:{value}' for name, value in metrics['counters'].items())}\n",
                "metrics.histograms="
                f"{','.join(sorted(metrics['histograms']))}\n",
            ]
        )
    lines.extend(
        [
            "\n",
        *traceback.format_exception(type(error), error, error.__traceback__),
        ]
    )
    crash_path.write_text("".join(lines), encoding="utf-8")
    increment_counter("crashes_written")
    return crash_path
