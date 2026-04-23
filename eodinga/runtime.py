from __future__ import annotations

import signal
from collections.abc import Iterator
from contextlib import contextmanager
from types import FrameType
from typing import Any


class ShutdownRequested(KeyboardInterrupt):
    def __init__(self, signum: int) -> None:
        self.signum = signum
        super().__init__(f"shutdown requested via signal {signum}")


def _raise_shutdown(signum: int, _frame: FrameType | None) -> None:
    raise ShutdownRequested(signum)


@contextmanager
def install_shutdown_handlers() -> Iterator[None]:
    previous_handlers: list[tuple[int, Any]] = []
    for name in ("SIGINT", "SIGTERM"):
        signum = getattr(signal, name, None)
        if signum is None:
            continue
        previous_handlers.append((signum, signal.getsignal(signum)))
        signal.signal(signum, _raise_shutdown)
    try:
        yield
    finally:
        for signum, handler in reversed(previous_handlers):
            signal.signal(signum, handler)


__all__ = ["ShutdownRequested", "install_shutdown_handlers"]
