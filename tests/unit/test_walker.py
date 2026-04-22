from __future__ import annotations

import os
from pathlib import Path
from stat import S_IFDIR, S_IFREG

import pytest

import eodinga.core.walker as walker_module
from eodinga.common import PathRules
from eodinga.core.walker import walk_batched


def test_walk_batched_visits_files_once_and_avoids_symlink_loop(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    root.mkdir()
    for index in range(120):
        folder = root / f"dir-{index // 20}"
        folder.mkdir(exist_ok=True)
        (folder / f"file-{index}.txt").write_text(f"content-{index}", encoding="utf-8")
    (root / "dir-0" / "loop").symlink_to(root, target_is_directory=True)

    before = sorted(path.relative_to(root) for path in root.rglob("*") if path.is_file())
    rules = PathRules(root=root, include=(str(root), f"{root}/**"), exclude=("**/loop/**",))
    batches = list(walk_batched(root, rules))
    file_paths = [
        record.path
        for batch in batches
        for record in batch
        if not record.is_dir and not record.is_symlink
    ]
    after = sorted(path.relative_to(root) for path in root.rglob("*") if path.is_file())

    assert len(file_paths) == 120
    assert len(set(file_paths)) == 120
    assert before == after


def test_walk_batched_reuses_discovery_stat_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "tree"
    nested = root / "nested"
    nested.mkdir(parents=True)
    sample = nested / "sample.txt"
    sample.write_text("sample", encoding="utf-8")

    stat_calls: list[Path] = []
    original_stat_safe = walker_module.stat_safe

    def counting_stat(path: Path) -> os.stat_result:
        stat_calls.append(path)
        return original_stat_safe(path)

    monkeypatch.setattr(walker_module, "stat_safe", counting_stat)

    rules = PathRules(root=root, include=(str(root), f"{root}/**"), exclude=())
    records = [record for batch in walk_batched(root, rules) for record in batch]

    assert {record.path for record in records} == {root, nested, sample}
    assert stat_calls.count(root) == 1
    assert stat_calls.count(nested) == 1
    assert stat_calls.count(sample) == 1


def test_walk_batched_keeps_distinct_hardlink_paths(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    root.mkdir()
    original = root / "original.txt"
    original.write_text("same inode", encoding="utf-8")
    linked = root / "linked.txt"
    os.link(original, linked)

    rules = PathRules(root=root, include=(str(root), f"{root}/**"), exclude=())
    records = [record for batch in walk_batched(root, rules) for record in batch]
    file_paths = {record.path.name for record in records if not record.is_dir}

    assert file_paths == {"original.txt", "linked.txt"}


def test_walk_batched_records_directory_alias_but_skips_reentering_same_inode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "tree"
    real = root / "real"
    alias = root / "real" / "mirror"
    sample = real / "sample.txt"

    def fake_stat(path: Path) -> os.stat_result:
        inode_map = {
            root: (S_IFDIR | 0o755, 1),
            real: (S_IFDIR | 0o755, 2),
            alias: (S_IFDIR | 0o755, 2),
            sample: (S_IFREG | 0o644, 3),
        }
        mode, inode = inode_map[path]
        return os.stat_result((mode, inode, 1, 1, 1000, 1000, 1, 1, 1, 1))

    def fake_scandir(path: Path) -> list[Path]:
        children = {
            root: [real],
            real: [sample, alias],
            alias: [sample, alias],
        }
        return children.get(path, [])

    monkeypatch.setattr(walker_module, "resolve_safe", lambda path: path)
    monkeypatch.setattr(walker_module, "stat_safe", fake_stat)
    monkeypatch.setattr(walker_module, "scandir_safe", fake_scandir)

    rules = PathRules(root=root, include=(str(root), f"{root}/**"), exclude=())
    records = [record for batch in walk_batched(root, rules) for record in batch]
    paths = [record.path for record in records]

    assert paths.count(real) == 1
    assert paths.count(alias) == 1
    assert paths.count(sample) == 1


def test_walk_batched_honors_symlink_alias_excludes(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    real = root / "real"
    alias = root / "alias"
    root.mkdir()
    real.mkdir()
    (real / "sample.txt").write_text("sample", encoding="utf-8")
    alias.symlink_to(real, target_is_directory=True)

    rules = PathRules(
        root=root,
        include=(str(root), f"{root}/**"),
        exclude=("**/alias", "**/alias/**"),
    )
    records = [record for batch in walk_batched(root, rules) for record in batch]
    paths = {record.path.relative_to(root) for record in records}

    assert Path("real") in paths
    assert Path("real/sample.txt") in paths
    assert Path("alias") not in paths
