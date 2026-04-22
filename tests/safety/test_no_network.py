from __future__ import annotations

import ast
from pathlib import Path


_BANNED_IMPORTS = {
    "http",
    "requests",
    "socket",
    "urllib.request",
}
_BANNED_CALLS = {
    "socket.socket",
    "urllib.request.urlopen",
}


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        if parent is None:
            return None
        return f"{parent}.{node.attr}"
    return None


def _scan_python_source(path: Path, root: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in _BANNED_IMPORTS or alias.name.startswith("http."):
                    violations.append(f"{path.relative_to(root)}:{node.lineno}:import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module in _BANNED_IMPORTS or module.startswith("http."):
                imported = ", ".join(alias.name for alias in node.names)
                violations.append(f"{path.relative_to(root)}:{node.lineno}:from {module} import {imported}")
        elif isinstance(node, ast.Call):
            dotted = _dotted_name(node.func)
            if dotted in _BANNED_CALLS:
                violations.append(f"{path.relative_to(root)}:{node.lineno}:{dotted}")

    return violations


def test_no_network_in_source() -> None:
    root = Path(__file__).resolve().parents[2]
    banned = (
        "ht" "tp://",
        "ht" "tps://",
        "requ" "ests",
        "urllib.request." "urlopen",
        "socket." "socket",
    )
    allowed_suffixes = {".py", ".toml", ".yml", ".yaml", ".ini", ".cfg", ".json"}
    skipped_parts = {".git", ".venv", "__pycache__", "tests/fixtures", "tests/safety/test_no_network.py"}
    violations: list[str] = []

    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in allowed_suffixes:
            continue
        normalized = path.as_posix()
        if any(part in normalized for part in skipped_parts):
            continue
        if path.suffix == ".py":
            violations.extend(_scan_python_source(path, root))

        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if "# noqa: eodinga-no-network" in stripped:
                continue
            if any(token in stripped for token in banned):
                violations.append(f"{path.relative_to(root)}:{lineno}:{stripped}")

    assert violations == []
