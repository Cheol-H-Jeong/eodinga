from __future__ import annotations

from pathlib import Path


def test_no_network_in_source() -> None:
    root = Path(__file__).resolve().parents[2]
    banned = (
        "ht" "tp",
        "ht" "tps",
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
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if "# noqa: eodinga-no-network" in stripped:
                continue
            if any(token in stripped for token in banned):
                violations.append(f"{path.relative_to(root)}:{lineno}:{stripped}")

    assert violations == []
