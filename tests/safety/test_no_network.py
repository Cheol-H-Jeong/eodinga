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
_SKIPPED_DIRS = {".git", ".pytest_cache", ".venv", "__pycache__"}
_SKIPPED_PATHS = {"tests/safety/test_no_network.py"}
_SKIPPED_PREFIXES = {"packaging/dist/", "tests/fixtures/"}
_SKIPPED_SUFFIXES = {
    ".db",
    ".dll",
    ".docx",
    ".epub",
    ".exe",
    ".hwp",
    ".ico",
    ".png",
    ".pdf",
    ".pptx",
    ".pyc",
    ".shm",
    ".sqlite3",
    ".svg",
    ".wal",
    ".xlsx",
}
_MAX_SCAN_BYTES = 1_000_000


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


def _should_skip(path: Path, root: Path) -> bool:
    relative = path.relative_to(root).as_posix()
    if relative in _SKIPPED_PATHS:
        return True
    if any(relative.startswith(prefix) for prefix in _SKIPPED_PREFIXES):
        return True
    return any(part in _SKIPPED_DIRS for part in path.parts)


def _is_text_candidate(path: Path) -> bool:
    if path.suffix.lower() in _SKIPPED_SUFFIXES:
        return False
    try:
        sample = path.read_bytes()
    except OSError:
        return False
    if len(sample) > _MAX_SCAN_BYTES:
        return False
    return b"\x00" not in sample


def test_no_network_in_source() -> None:
    root = Path(__file__).resolve().parents[2]
    banned = (
        "ht" "tp://",
        "ht" "tps://",
        "requ" "ests",
        "urllib.request." "urlopen",
        "socket." "socket",
    )
    violations: list[str] = []

    for path in root.rglob("*"):
        if not path.is_file() or _should_skip(path, root) or not _is_text_candidate(path):
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
