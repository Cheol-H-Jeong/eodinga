from __future__ import annotations

from pathlib import Path

import pytest

from eodinga.core import fs


def test_fs_exports_are_exact() -> None:
    assert set(fs.__all__) == {
        "DENYLIST",
        "ScandirEntry",
        "is_hidden",
        "open_readonly",
        "resolve_safe",
        "scandir_entries_safe",
        "scandir_safe",
        "stat_follow_safe",
        "stat_safe",
    }


def test_open_readonly_rejects_write_mode(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    target.write_text("hello", encoding="utf-8")
    with pytest.raises(ValueError):
        fs.open_readonly(target, mode="w")  # type: ignore[arg-type]


def test_scandir_entries_safe_returns_cached_child_metadata(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    root.mkdir()
    sample = root / "sample.txt"
    sample.write_text("sample", encoding="utf-8")

    entries = list(fs.scandir_entries_safe(root))

    assert len(entries) == 1
    assert entries[0].path == sample
    assert entries[0].stat_result is not None
    assert entries[0].stat_result.st_size == len("sample")
