from __future__ import annotations

from pathlib import Path

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
