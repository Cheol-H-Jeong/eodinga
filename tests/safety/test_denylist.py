from __future__ import annotations

from pathlib import Path

from eodinga.common import PathRules
from eodinga.core.rules import should_index


def test_default_denylist_blocks_system_paths() -> None:
    rules = PathRules()

    blocked_paths = (
        Path("/proc/cpuinfo"),
        Path("/sys/kernel"),
        Path("/snap/eodinga/current"),
        Path("/tmp/eodinga-cache/file.txt"),
        Path("C:/Windows/System32/kernel32.dll"),
    )

    assert all(not should_index(path, rules) for path in blocked_paths)
