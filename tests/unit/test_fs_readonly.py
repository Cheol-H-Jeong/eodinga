from __future__ import annotations

from pathlib import Path

import pytest

from eodinga.core import fs


def test_fs_exports_are_exact() -> None:
    assert set(fs.__all__) == {
        "DENYLIST",
        "ScanEntry",
        "is_hidden",
        "open_readonly",
        "resolve_safe",
        "scandir_safe",
        "scandir_with_stat_safe",
        "stat_follow_safe",
        "stat_safe",
    }


def test_open_readonly_rejects_write_mode(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    target.write_text("hello", encoding="utf-8")
    with pytest.raises(ValueError):
        fs.open_readonly(target, mode="w")  # type: ignore[arg-type]
