from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from loguru import logger


def configure_logging(level: str = "INFO", log_path: Path | None = None) -> None:
    logger.remove()
    logger.add(sys.stderr, level=level.upper())
    if log_path is not None:
        logger.add(log_path, rotation="5 MB", retention=5, level=level.upper())


def get_logger(name: str) -> Any:
    return logger.bind(component=name)


def record_counter(name: str, value: int = 1, **fields: object) -> None:
    logger.bind(metric=name, **fields).debug("counter +{value}", value=value)


def record_snapshot(name: str, payload: Mapping[str, object]) -> None:
    logger.bind(metric=name, payload=dict(payload)).debug("snapshot recorded")
