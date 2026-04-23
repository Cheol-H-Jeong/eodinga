from __future__ import annotations

from pathlib import Path

import pytest

import eodinga.core.rules as rules_module
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


def test_user_exclude_glob_applies_to_symlink_alias_paths(tmp_path: Path) -> None:
    root = tmp_path / "root"
    real = root / "real"
    alias = root / "alias"
    target = alias / "artifact.txt"
    real.mkdir(parents=True)
    (real / "artifact.txt").write_text("x", encoding="utf-8")
    alias.symlink_to(real, target_is_directory=True)

    rules = PathRules(
        root=root,
        include=(str(root), f"{root}/**"),
        exclude=("**/alias", "**/alias/**"),
    )

    assert not should_index(alias, rules)
    assert not should_index(target, rules)


def test_user_include_overrides_default_denylist() -> None:
    rules = PathRules(include=("/tmp/project/**",))
    assert should_index(Path("/tmp/project/file.txt"), rules)


def test_explicit_root_overrides_default_denylist(tmp_path: Path) -> None:
    root = tmp_path / "project"
    target = root / "notes.txt"
    target.parent.mkdir(parents=True)
    target.write_text("hello\n", encoding="utf-8")

    rules = PathRules(root=root)

    assert should_index(root, rules)
    assert should_index(target, rules)


def test_should_index_caches_compiled_include_and_exclude_specs(monkeypatch: pytest.MonkeyPatch) -> None:
    compiled_patterns: list[tuple[str, ...]] = []
    original_compile = rules_module.PathSpec.from_lines

    def counting_compile(pattern_factory: str, patterns: list[str]) -> rules_module.PathSpec:
        assert pattern_factory == "gitignore"
        compiled_patterns.append(tuple(patterns))
        return original_compile(pattern_factory, patterns)

    rules_module._compile.cache_clear()
    monkeypatch.setattr(rules_module.PathSpec, "from_lines", counting_compile)

    rules = PathRules(
        root=Path("/workspace"),
        include=("/workspace", "/workspace/**"),
        exclude=("**/.git/**",),
    )

    assert should_index(Path("/workspace/docs/readme.md"), rules)
    assert not should_index(Path("/workspace/.git/config"), rules)
    assert should_index(Path("/workspace/src/main.py"), rules)

    assert compiled_patterns == [
        ("/workspace", "/workspace/**"),
        ("**/.git/**",),
    ]
