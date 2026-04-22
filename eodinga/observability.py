from __future__ import annotations

from collections import Counter
from typing import Final

from loguru import logger as _logger

_COUNTERS: Final[Counter[str]] = Counter()
logger = _logger


def increment_counter(name: str) -> None:
    _COUNTERS[name] += 1


def get_counter_value(name: str) -> int:
    return _COUNTERS[name]
