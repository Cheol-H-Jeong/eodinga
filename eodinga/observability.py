from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from statistics import fmean
from threading import Lock

from loguru import logger

_COUNTERS: defaultdict[str, int] = defaultdict(int)
_HISTOGRAMS: defaultdict[str, list[float]] = defaultdict(list)
_LOCK = Lock()


def configure_logging(level: str = "INFO") -> None:
    logger.remove()
    logger.add(lambda message: None, level=level)


@dataclass(slots=True)
class _Counter:
    name: str

    def inc(self, n: int = 1) -> None:
        with _LOCK:
            _COUNTERS[self.name] += n


@dataclass(slots=True)
class _Histogram:
    name: str

    def observe(self, value: float) -> None:
        with _LOCK:
            _HISTOGRAMS[self.name].append(value)


def counter(name: str) -> _Counter:
    return _Counter(name=name)


def histogram(name: str) -> _Histogram:
    return _Histogram(name=name)


def snapshot() -> dict[str, object]:
    with _LOCK:
        return {
            "counters": dict(_COUNTERS),
            "histograms": {
                name: {"count": len(values), "avg": fmean(values) if values else 0.0}
                for name, values in _HISTOGRAMS.items()
            },
        }
