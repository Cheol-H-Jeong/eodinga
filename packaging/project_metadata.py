from __future__ import annotations

import argparse
import json
import shlex
import tomllib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = PROJECT_ROOT / "pyproject.toml"


def _normalize_author_name(authors: object) -> str:
    if not isinstance(authors, list) or not authors:
        raise ValueError("pyproject.toml project.authors must contain at least one author")
    first = authors[0]
    if not isinstance(first, dict):
        raise ValueError("pyproject.toml project.authors entries must be tables")
    name = first.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError("pyproject.toml project.authors[0].name is missing")
    return name


def _debian_python_dependency(requires_python: str) -> str:
    normalized = requires_python.strip()
    if not normalized.startswith(">="):
        raise ValueError("pyproject.toml project.requires-python must start with >=")
    return f"python3 ({normalized})"


def read_project_metadata(pyproject_path: Path = PYPROJECT) -> dict[str, str]:
    payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = payload["project"]
    name = str(project["name"])
    version = str(project["version"])
    description = str(project["description"])
    requires_python = str(project["requires-python"])
    publisher = _normalize_author_name(project.get("authors"))
    return {
        "name": name,
        "version": version,
        "description": description,
        "publisher": publisher,
        "requires_python": requires_python,
        "debian_python_dependency": _debian_python_dependency(requires_python),
    }


def _shell_assignment(key: str, value: str) -> str:
    return f"{key}={shlex.quote(value)}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=("json", "shell"), default="json")
    args = parser.parse_args(argv)

    metadata = read_project_metadata()
    if args.format == "json":
        print(json.dumps(metadata, indent=2))
        return 0

    for key, value in metadata.items():
        shell_key = f"PROJECT_{key.upper()}"
        print(_shell_assignment(shell_key, value))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
