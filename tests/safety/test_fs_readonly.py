from __future__ import annotations

import ast
from pathlib import Path

import pytest

from eodinga.core import fs


def test_fs_wrapper_has_no_write_ops() -> None:
    forbidden = {"rename", "unlink", "write_text", "write_bytes", "copy", "chmod", "truncate"}
    assert forbidden.isdisjoint(set(dir(fs)))


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        if parent is None:
            return None
        return f"{parent}.{node.attr}"
    return None


def test_fs_module_avoids_write_capable_calls() -> None:
    source = Path(fs.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=fs.__file__ or "eodinga/core/fs.py")
    forbidden_methods = {
        "chmod",
        "mkdir",
        "rename",
        "replace",
        "rmdir",
        "symlink",
        "truncate",
        "unlink",
        "write_bytes",
        "write_text",
    }
    forbidden_calls = {
        "os.remove",
        "os.rename",
        "os.replace",
        "shutil.copy",
        "shutil.copy2",
    }

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        dotted = _dotted_name(node.func)
        assert dotted not in forbidden_calls
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, (ast.Name, ast.Attribute)):
            assert node.func.attr not in forbidden_methods


@pytest.mark.parametrize("mode", ["w", "wb", "a", "ab", "x", "xb", "r+", "rb+", "a+"])
def test_open_readonly_rejects_all_write_capable_modes(tmp_path: Path, mode: str) -> None:
    target = tmp_path / "fixture.txt"
    target.write_text("hello", encoding="utf-8")

    with pytest.raises(ValueError):
        fs.open_readonly(target, mode=mode)  # type: ignore[arg-type]
