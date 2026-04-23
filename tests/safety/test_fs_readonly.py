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


def _collect_import_aliases(tree: ast.AST) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local_name = alias.asname or alias.name.split(".", 1)[0]
                aliases[local_name] = alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                local_name = alias.asname or alias.name
                aliases[local_name] = f"{module}.{alias.name}" if module else alias.name
    return aliases


def _resolve_dotted_name(node: ast.AST, aliases: dict[str, str]) -> str | None:
    dotted = _dotted_name(node)
    if dotted is None:
        return None
    head, _, tail = dotted.partition(".")
    resolved_head = aliases.get(head, head)
    if not tail:
        return resolved_head
    return f"{resolved_head}.{tail}"


def _literal_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _mode_is_write_capable(mode: str | None) -> bool:
    return mode is None or any(flag in mode for flag in ("w", "a", "+", "x", "U"))


def _contains_write_open_flags(node: ast.AST, aliases: dict[str, str] | None = None) -> bool:
    aliases = {} if aliases is None else aliases
    write_flags = {
        "O_APPEND",
        "O_CREAT",
        "O_EXCL",
        "O_RDWR",
        "O_TRUNC",
        "O_WRONLY",
    }
    if isinstance(node, ast.Attribute):
        return node.attr in write_flags
    if isinstance(node, ast.Name):
        resolved = aliases.get(node.id, node.id)
        return resolved.rsplit(".", 1)[-1] in write_flags
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _contains_write_open_flags(node.left, aliases) or _contains_write_open_flags(
            node.right, aliases
        )
    return False


def test_fs_module_avoids_write_capable_calls() -> None:
    source = Path(fs.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=fs.__file__ or "eodinga/core/fs.py")
    aliases = _collect_import_aliases(tree)
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
        "open",
        "os.fdopen",
        "os.open",
        "os.remove",
        "os.rename",
        "os.replace",
        "shutil.copy",
        "shutil.copy2",
    }

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        dotted = _resolve_dotted_name(node.func, aliases)
        if dotted == "os.open" and len(node.args) >= 2:
            assert not _contains_write_open_flags(node.args[1], aliases)
            continue
        if dotted == "os.fdopen":
            mode: str | None = None
            if len(node.args) >= 2:
                mode = _literal_string(node.args[1])
            for keyword in node.keywords:
                if keyword.arg == "mode":
                    mode = _literal_string(keyword.value)
                    break
            assert not _mode_is_write_capable(mode)
            continue
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
                    assert not _mode_is_write_capable(mode)


def test_write_flag_detector_catches_os_open_write_modes() -> None:
    node = ast.parse("os.open(path, os.O_WRONLY | os.O_CREAT)").body[0]
    assert isinstance(node, ast.Expr)
    assert isinstance(node.value, ast.Call)
    assert _contains_write_open_flags(node.value.args[1]) is True

    safe = ast.parse("os.open(path, os.O_RDONLY)").body[0]
    assert isinstance(safe, ast.Expr)
    assert isinstance(safe.value, ast.Call)
    assert _contains_write_open_flags(safe.value.args[1]) is False


def test_write_flag_detector_resolves_imported_flag_aliases() -> None:
    tree = ast.parse("from os import O_WRONLY as WRONLY, O_CREAT as CREATE\nos.open(path, WRONLY | CREATE)")
    aliases = _collect_import_aliases(tree)
    node = tree.body[1]
    assert isinstance(node, ast.Expr)
    assert isinstance(node.value, ast.Call)

    assert _contains_write_open_flags(node.value.args[1], aliases) is True


def test_alias_resolution_catches_imported_write_calls() -> None:
    tree = ast.parse("from os import open as os_open\nos_open(path, os.O_RDONLY)")
    aliases = _collect_import_aliases(tree)
    node = tree.body[1]
    assert isinstance(node, ast.Expr)
    assert isinstance(node.value, ast.Call)

    assert _resolve_dotted_name(node.value.func, aliases) == "os.open"


def test_mode_detector_treats_fdopen_without_literal_mode_as_write_capable() -> None:
    assert _mode_is_write_capable(None) is True
    assert _mode_is_write_capable("rb") is False
    assert _mode_is_write_capable("w") is True


@pytest.mark.parametrize("mode", ["w", "wb", "a", "ab", "x", "xb", "r+", "rb+", "a+"])
def test_open_readonly_rejects_all_write_capable_modes(tmp_path: Path, mode: str) -> None:
    target = tmp_path / "fixture.txt"
    target.write_text("hello", encoding="utf-8")

    with pytest.raises(ValueError):
        fs.open_readonly(target, mode=mode)  # type: ignore[arg-type]


@pytest.mark.parametrize("mode", ["", "b", "t", "rr", "rbb", "rtt", "rbt", "rtb"])
def test_open_readonly_rejects_ambiguous_non_read_modes(tmp_path: Path, mode: str) -> None:
    target = tmp_path / "fixture.txt"
    target.write_text("hello", encoding="utf-8")

    with pytest.raises(ValueError):
        fs.open_readonly(target, mode=mode)  # type: ignore[arg-type]
