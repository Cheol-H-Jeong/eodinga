from __future__ import annotations

import re
from pathlib import Path


def test_fs_source_contains_no_write_operations() -> None:
    source = Path("eodinga/core/fs.py").read_text(encoding="utf-8")
    forbidden = [
        r"os\.remove",
        r"os\.unlink",
        r"os\.rename",
        r"shutil\.move",
        r"shutil\.copy",
        r"open.*[\"']w",
        r"Path\.write",
        r"Path\.rename",
        r"Path\.unlink",
    ]
    for pattern in forbidden:
        assert re.search(pattern, source) is None, pattern
