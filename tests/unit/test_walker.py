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


def test_walk_batched_reuses_scandir_stat_result_for_children(
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
    assert nested not in stat_calls
    assert sample not in stat_calls


def test_walk_batched_uses_fs_wrapper_to_detect_symlinked_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "tree"
    real = root / "real"
    alias = root / "alias"
    root.mkdir()
    real.mkdir()
    alias.symlink_to(real, target_is_directory=True)

    follow_calls: list[Path] = []
    original_follow_stat = walker_module.stat_follow_safe

    def counting_follow_stat(path: Path) -> os.stat_result:
        follow_calls.append(path)
        return original_follow_stat(path)

    def fail_is_dir(self: Path) -> bool:
        raise AssertionError("walker should use eodinga.core.fs.stat_follow_safe")

    monkeypatch.setattr(walker_module, "stat_follow_safe", counting_follow_stat)
    monkeypatch.setattr(Path, "is_dir", fail_is_dir)

    rules = PathRules(root=root, include=(str(root), f"{root}/**"), exclude=())
    records = [record for batch in walk_batched(root, rules) for record in batch]
    alias_record = next(record for record in records if record.path == alias)

    assert alias_record.is_symlink is True
    assert alias_record.is_dir is True
    assert follow_calls == [alias]


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

    def fake_scandir(path: Path) -> list[tuple[Path, os.stat_result]]:
        children = {
            root: [(real, fake_stat(real))],
            real: [(sample, fake_stat(sample)), (alias, fake_stat(alias))],
            alias: [(sample, fake_stat(sample)), (alias, fake_stat(alias))],
        }
        return children.get(path, [])

    monkeypatch.setattr(walker_module, "resolve_safe", lambda path: path)
    monkeypatch.setattr(walker_module, "stat_safe", fake_stat)
    monkeypatch.setattr(walker_module, "scandir_with_stat_safe", fake_scandir)

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


def test_walk_batched_indexes_symlinked_root_using_alias_paths(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    (real / "docs").mkdir()
    (real / "docs" / "guide.txt").write_text("guide", encoding="utf-8")
    alias = tmp_path / "alias"
    alias.symlink_to(real, target_is_directory=True)

    rules = PathRules(root=alias, include=(str(alias), f"{alias}/**"), exclude=())
    records = [record for batch in walk_batched(alias, rules) for record in batch]
    paths = {record.path for record in records}
    record_by_path = {record.path: record for record in records}

    assert alias in paths
    assert alias / "docs" in paths
    assert alias / "docs" / "guide.txt" in paths
    assert all(str(path).startswith(str(alias)) for path in paths)
    assert record_by_path[alias].is_symlink is True
    assert record_by_path[alias].is_dir is True


def test_walk_batched_marks_symlinked_directories_as_directories(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    real = root / "real"
    alias = root / "alias"
    root.mkdir()
    real.mkdir()
    alias.symlink_to(real, target_is_directory=True)

    rules = PathRules(root=root, include=(str(root), f"{root}/**"), exclude=())
    records = [record for batch in walk_batched(root, rules) for record in batch]
    alias_record = next(record for record in records if record.path == alias)

    assert alias_record.is_symlink is True
    assert alias_record.is_dir is True


def test_walk_batched_skips_resolved_alias_cycles_even_when_inode_keys_differ(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "tree"
    canonical = root / "canonical"
    mirror = root / "mirror"
    sample = canonical / "sample.txt"

    def fake_stat(path: Path) -> os.stat_result:
        inode_map = {
            root: (10, 1, S_IFDIR | 0o755),
            canonical: (10, 2, S_IFDIR | 0o755),
            mirror: (11, 200, S_IFDIR | 0o755),
            sample: (10, 3, S_IFREG | 0o644),
        }
        device, inode, mode = inode_map[path]
        return os.stat_result((mode, inode, device, 1, 1000, 1000, 1, 1, 1, 1))

    def fake_scandir(path: Path) -> list[tuple[Path, os.stat_result]]:
        children = {
            root: [(canonical, fake_stat(canonical))],
            canonical: [(sample, fake_stat(sample)), (mirror, fake_stat(mirror))],
            mirror: [(sample, fake_stat(sample)), (mirror, fake_stat(mirror))],
        }
        return children.get(path, [])

    def fake_resolve(path: Path) -> Path:
        return canonical if path == mirror else path

    monkeypatch.setattr(walker_module, "resolve_safe", fake_resolve)
    monkeypatch.setattr(walker_module, "stat_safe", fake_stat)
    monkeypatch.setattr(walker_module, "scandir_with_stat_safe", fake_scandir)

    rules = PathRules(root=root, include=(str(root), f"{root}/**"), exclude=())
    records = [record for batch in walk_batched(root, rules) for record in batch]
    paths = [record.path for record in records]

    assert paths.count(canonical) == 1
    assert paths.count(mirror) == 1
    assert paths.count(sample) == 1


def test_walk_batched_skips_descending_when_resolve_safe_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "tree"
    child = root / "child"
    nested = child / "nested.txt"
    root.mkdir()
    child.mkdir()
    nested.write_text("nested", encoding="utf-8")

    original_resolve_safe = walker_module.resolve_safe

    def flaky_resolve(path: Path) -> Path:
        if path == child:
            raise OSError("bind mount disappeared")
        return original_resolve_safe(path)

    monkeypatch.setattr(walker_module, "resolve_safe", flaky_resolve)

    rules = PathRules(root=root, include=(str(root), f"{root}/**"), exclude=())
    records = [record for batch in walk_batched(root, rules) for record in batch]
    paths = {record.path for record in records}

    assert root in paths
    assert child in paths
    assert nested not in paths
