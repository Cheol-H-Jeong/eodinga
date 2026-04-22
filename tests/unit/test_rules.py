from __future__ import annotations

from pathlib import Path

from eodinga.common import PathRules
from eodinga.core.rules import should_index


def test_default_denylist_blocks_linux_system_paths() -> None:
    rules = PathRules()
    assert not should_index(Path("/proc/cpuinfo"), rules)
    assert not should_index(Path("/sys/kernel"), rules)


def test_default_denylist_blocks_windows_system_paths() -> None:
    rules = PathRules()
    assert not should_index(Path("C:/Windows/System32/kernel32.dll"), rules)


def test_user_exclude_glob_applies(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    target = root / "build" / "artifact.txt"
    target.parent.mkdir()
    target.write_text("x", encoding="utf-8")
    rules = PathRules(root=root, include=("**/*",), exclude=("**/build/**",))
    assert not should_index(target, rules)


def test_user_include_overrides_default_denylist() -> None:
    rules = PathRules(include=("/tmp/project/**",))
    assert should_index(Path("/tmp/project/file.txt"), rules)
