from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter

from loguru import logger


def get_logger():
    return logger.bind(component="eodinga")


@contextmanager
def observe_timing(metric_name: str) -> Iterator[None]:
    start = perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (perf_counter() - start) * 1000
        get_logger().debug("{metric}={elapsed_ms:.2f}ms", metric=metric_name, elapsed_ms=elapsed_ms)

