from __future__ import annotations

import ast
import shlex
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
    "asyncio.create_subprocess_shell",
    "asyncio.open_connection",
    "http.client.HTTPConnection",
    "http.client.HTTPSConnection",
    "httpx.Client",
    "httpx.AsyncClient",
    "os.popen",
    "os.system",
    "socket.create_connection",
    "socket.socket",
    "urllib.request.urlopen",
}
_BANNED_EXEC_CALLS = {"asyncio.create_subprocess_exec"}
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


def _string_literal(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _subprocess_command_name(node: ast.AST) -> str | None:
    if isinstance(node, (ast.List, ast.Tuple)) and node.elts:
        return _string_literal(node.elts[0])
    return _string_literal(node)


def _shell_uses_banned_command(command: str) -> str | None:
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        tokens = command.split()
    for token in tokens:
        base = Path(token).name.lower()
        if base.endswith(".exe"):
            base = base[:-4]
        if base in _BANNED_SUBPROCESS_COMMANDS:
            return base
    return None


def _normalize_command_name(command: str) -> str:
    base = Path(command).name.lower()
    if base.endswith(".exe"):
        return base[:-4]
    return base


def _scan_python_source(path: Path, root: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    aliases = _collect_import_aliases(tree)
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in _BANNED_IMPORTS or alias.name.startswith("http."):
                    violations.append(f"{path.relative_to(root)}:{node.lineno}:import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imported = ", ".join(alias.name for alias in node.names)
            full_targets = [
                f"{module}.{alias.name}" if module else alias.name for alias in node.names
            ]
            if (
                module in _BANNED_IMPORTS
                or module.startswith("http.")
                or any(target in _BANNED_IMPORTS or target.startswith("http.") for target in full_targets)
            ):
                violations.append(f"{path.relative_to(root)}:{node.lineno}:from {module} import {imported}")
        elif isinstance(node, ast.Call):
            dotted = _resolve_dotted_name(node.func, aliases)
            if dotted in _BANNED_CALLS:
                if node.args:
                    command = _subprocess_command_name(node.args[0])
                    if command is not None:
                        shell_command = _shell_uses_banned_command(command)
                        if shell_command is not None:
                            violations.append(
                                f"{path.relative_to(root)}:{node.lineno}:subprocess {shell_command}"
                            )
                            continue
                violations.append(f"{path.relative_to(root)}:{node.lineno}:{dotted}")
            if dotted in _BANNED_EXEC_CALLS and node.args:
                command = _subprocess_command_name(node.args[0])
                if command is not None and _normalize_command_name(command) in _BANNED_SUBPROCESS_COMMANDS:
                    violations.append(
                        f"{path.relative_to(root)}:{node.lineno}:subprocess {_normalize_command_name(command)}"
                    )
                    continue
            if dotted in {
                "subprocess.run",
                "subprocess.call",
                "subprocess.check_call",
                "subprocess.check_output",
                "subprocess.Popen",
            } and node.args:
                command = _subprocess_command_name(node.args[0])
                normalized_command = (
                    _normalize_command_name(command) if command is not None else None
                )
                if normalized_command in _BANNED_SUBPROCESS_COMMANDS:
                    violations.append(
                        f"{path.relative_to(root)}:{node.lineno}:subprocess {normalized_command}"
                    )
                    continue
                shell_mode = any(
                    keyword.arg == "shell"
                    and isinstance(keyword.value, ast.Constant)
                    and keyword.value.value is True
                    for keyword in node.keywords
                )
                if command is not None and shell_mode:
                    shell_command = _shell_uses_banned_command(command)
                    if shell_command is not None:
                        violations.append(
                            f"{path.relative_to(root)}:{node.lineno}:subprocess {shell_command}"
                        )

    return violations


def test_shell_command_scanner_flags_curl_and_wget_variants() -> None:
    assert _shell_uses_banned_command("curl https://example.com") == "curl"
    assert _shell_uses_banned_command("C:/Windows/System32/wget.exe https://example.com") == "wget"
    assert _shell_uses_banned_command("python -m http.server") is None


def test_python_source_scan_flags_shell_wrapped_network_commands(tmp_path: Path) -> None:
    source = tmp_path / "candidate.py"
    source.write_text(
        "import subprocess\n"
        "subprocess.run('curl https://example.com', shell=True)\n"
        "subprocess.Popen('wget.exe https://example.com', shell=True)\n",
        encoding="utf-8",
    )

    violations = _scan_python_source(source, tmp_path)

    assert violations == [
        "candidate.py:2:subprocess curl",
        "candidate.py:3:subprocess wget",
    ]


def test_python_source_scan_flags_list_form_network_commands_with_absolute_paths(
    tmp_path: Path,
) -> None:
    source = tmp_path / "candidate.py"
    source.write_text(
        "import subprocess\n"
        "subprocess.run(['/usr/bin/curl', 'https://example.com'])\n"
        "subprocess.Popen((r'C:/Windows/System32/wget.exe', 'https://example.com'))\n",
        encoding="utf-8",
    )

    violations = _scan_python_source(source, tmp_path)

    assert violations == [
        "candidate.py:2:subprocess curl",
        "candidate.py:3:subprocess wget",
    ]


def test_python_source_scan_flags_shell_wrapped_network_commands_outside_subprocess(
    tmp_path: Path,
) -> None:
    source = tmp_path / "candidate.py"
    source.write_text(
        "import asyncio\n"
        "import os\n"
        "os.system('curl https://example.com')\n"
        "os.popen('wget https://example.com')\n"
        "asyncio.create_subprocess_shell('curl https://example.com')\n",
        encoding="utf-8",
    )

    violations = _scan_python_source(source, tmp_path)

    assert violations == [
        "candidate.py:3:subprocess curl",
        "candidate.py:4:subprocess wget",
        "candidate.py:5:subprocess curl",
    ]


def test_python_source_scan_flags_exec_style_network_commands(tmp_path: Path) -> None:
    source = tmp_path / "candidate.py"
    source.write_text(
        "import asyncio\n"
        "asyncio.create_subprocess_exec('curl', 'https://example.com')\n"
        "asyncio.create_subprocess_exec('wget.exe', 'https://example.com')\n",
        encoding="utf-8",
    )

    violations = _scan_python_source(source, tmp_path)

    assert violations == [
        "candidate.py:2:subprocess curl",
        "candidate.py:3:subprocess wget",
    ]


def test_python_source_scan_flags_parent_module_imports_and_aliased_calls(tmp_path: Path) -> None:
    source = tmp_path / "candidate.py"
    source.write_text(
        "from urllib import request as request_module\n"
        "from http import client as http_client\n"
        "from socket import create_connection as connect\n"
        "request_module.urlopen('https://example.com')\n"
        "http_client.HTTPConnection('example.com')\n"
        "connect(('example.com', 443))\n",
        encoding="utf-8",
    )

    violations = _scan_python_source(source, tmp_path)

    assert violations == [
        "candidate.py:1:from urllib import request",
        "candidate.py:2:from http import client",
        "candidate.py:3:from socket import create_connection",
        "candidate.py:4:urllib.request.urlopen",
        "candidate.py:5:http.client.HTTPConnection",
        "candidate.py:6:socket.create_connection",
    ]


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
