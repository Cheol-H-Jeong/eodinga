from __future__ import annotations

from pathlib import Path

import pytest

from eodinga.core import fs


def test_fs_exports_are_exact() -> None:
    assert set(fs.__all__) == {
        "DENYLIST",
        "is_hidden",
        "open_readonly",
        "resolve_safe",
        "scandir_safe",
        "stat_follow_safe",
        "stat_safe",
    }


def test_open_readonly_rejects_write_mode(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    target.write_text("hello", encoding="utf-8")
    with pytest.raises(ValueError):
        fs.open_readonly(target, mode="w")  # type: ignore[arg-type]


def test_open_readonly_rejects_encoding_for_binary_mode(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    target.write_text("hello", encoding="utf-8")

    with pytest.raises(ValueError, match="binary mode"):
        fs.open_readonly(target, mode="rb", encoding="utf-8")


def test_open_readonly_allows_text_mode_with_encoding(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    target.write_text("hello", encoding="utf-8")

    with fs.open_readonly(target, mode="rt", encoding="utf-8") as handle:
        assert handle.read() == "hello"


@pytest.mark.parametrize("mode", ["", "b", "t", "rr", "rbb", "rtt", "rbt", "rtb", "rb+"])
def test_open_readonly_rejects_malformed_read_modes(tmp_path: Path, mode: str) -> None:
    target = tmp_path / "file.txt"
    target.write_text("hello", encoding="utf-8")

    with pytest.raises(ValueError):
        fs.open_readonly(target, mode=mode)  # type: ignore[arg-type]
