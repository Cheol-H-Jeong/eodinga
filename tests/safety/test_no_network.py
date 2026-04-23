from __future__ import annotations

import ast
from pathlib import Path


_BANNED_IMPORTS = {
    "aiohttp",
    "http",
    "http.client",
    "httpx",
    "requests",
    "socket",
    "urllib3",
    "urllib.request",
    "websocket",
    "websockets",
}
_BANNED_CALLS = {
    "asyncio.open_connection",
    "http.client.HTTPConnection",
    "http.client.HTTPSConnection",
    "os.system",
    "httpx.Client",
    "httpx.AsyncClient",
    "socket.create_connection",
    "socket.socket",
    "subprocess.getoutput",
    "subprocess.getstatusoutput",
    "urllib.request.urlopen",
}
_BANNED_SUBPROCESS_COMMANDS = {"curl", "wget"}
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


def _string_literal(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _subprocess_command_name(node: ast.AST) -> str | None:
    if isinstance(node, (ast.List, ast.Tuple)) and node.elts:
        return _string_literal(node.elts[0])
    return _string_literal(node)


def _collect_import_aliases(tree: ast.AST) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound_name = alias.asname or alias.name.split(".", 1)[0]
                aliases[bound_name] = alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                if alias.name == "*":
                    continue
                bound_name = alias.asname or alias.name
                aliases[bound_name] = f"{module}.{alias.name}" if module else alias.name
    return aliases


def _resolve_alias_dotted_name(name: str, aliases: dict[str, str]) -> str:
    head, separator, tail = name.partition(".")
    target = aliases.get(head)
    if target is None:
        return name
    if separator:
        return f"{target}.{tail}"
    return target


def _scan_python_source(path: Path, root: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[str] = []
    aliases = _collect_import_aliases(tree)

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
            if dotted is not None:
                dotted = _resolve_alias_dotted_name(dotted, aliases)
            if dotted in _BANNED_CALLS:
                violations.append(f"{path.relative_to(root)}:{node.lineno}:{dotted}")
            if dotted in {
                "subprocess.run",
                "subprocess.call",
                "subprocess.check_call",
                "subprocess.check_output",
                "subprocess.Popen",
            } and node.args:
                command = _subprocess_command_name(node.args[0])
                if command is not None and command.split(maxsplit=1)[0] in _BANNED_SUBPROCESS_COMMANDS:
                    violations.append(
                        f"{path.relative_to(root)}:{node.lineno}:subprocess {command}"
                    )

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
        "aio" "http",
        "ht" "tp://",
        "ht" "tps://",
        "http" ".client",
        "ht" "tpx",
        "requ" "ests",
        "socket." "create_connection",
        "urllib.request." "urlopen",
        "urlli" "b3",
        "web" "socket",
        "web" "sockets",
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
