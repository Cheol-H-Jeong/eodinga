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


def _collect_aliases(tree: ast.AST) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local_name = alias.asname or alias.name.split(".", maxsplit=1)[0]
                aliases[local_name] = alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                local_name = alias.asname or alias.name
                aliases[local_name] = f"{module}.{alias.name}" if module else alias.name
    return aliases


def _canonicalize_dotted_name(name: str | None, aliases: dict[str, str]) -> str | None:
    if name is None:
        return None
    head, *tail = name.split(".")
    target = aliases.get(head)
    if target is None:
        return name
    return ".".join((target, *tail))


def _literal_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def test_fs_module_avoids_write_capable_calls() -> None:
    source = Path(fs.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=fs.__file__ or "eodinga/core/fs.py")
    aliases = _collect_aliases(tree)
    forbidden_methods = {
        "chmod",
        "mkdir",
        "rename",
        "replace",
        "rmdir",
        "symlink",
        "touch",
        "truncate",
        "unlink",
        "write_bytes",
        "write_text",
    }
    forbidden_calls = {
        "builtins.open",
        "io.open",
        "open",
        "os.remove",
        "os.rename",
        "os.replace",
        "shutil.copy",
        "shutil.copy2",
    }

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        dotted = _canonicalize_dotted_name(_dotted_name(node.func), aliases)
        assert dotted not in forbidden_calls
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, (ast.Name, ast.Attribute)):
            assert node.func.attr not in forbidden_methods
            if node.func.attr == "open":
                mode: str | None = None
                if len(node.args) >= 1:
                    mode = _literal_string(node.args[0])
                for keyword in node.keywords:
                    if keyword.arg == "mode":
                        mode = _literal_string(keyword.value)
                        break
                if mode is not None:
                    assert all(flag not in mode for flag in ("w", "a", "+", "x"))


@pytest.mark.parametrize("mode", ["w", "wb", "a", "ab", "x", "xb", "r+", "rb+", "a+"])
def test_open_readonly_rejects_all_write_capable_modes(tmp_path: Path, mode: str) -> None:
    target = tmp_path / "fixture.txt"
    target.write_text("hello", encoding="utf-8")

    with pytest.raises(ValueError):
        fs.open_readonly(target, mode=mode)  # type: ignore[arg-type]
