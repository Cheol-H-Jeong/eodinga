from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT_DIR / "pyproject.toml"
PACKAGE_INIT = ROOT_DIR / "eodinga" / "__init__.py"
DEBIAN_CONTROL_TEMPLATE = ROOT_DIR / "packaging" / "linux" / "debian" / "control"
_VERSION_PATTERN = re.compile(r'^__version__\s*=\s*"(?P<version>[^"]+)"', re.MULTILINE)


def read_project_version() -> str:
    payload = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    return str(payload["project"]["version"])


def read_package_version() -> str:
    match = _VERSION_PATTERN.search(PACKAGE_INIT.read_text(encoding="utf-8"))
    if match is None:
        raise ValueError(f"could not determine package version from {PACKAGE_INIT}")
    return match.group("version")


def require_synced_versions() -> str:
    project_version = read_project_version()
    package_version = read_package_version()
    if project_version != package_version:
        raise ValueError(
            f"version mismatch between {PYPROJECT.name} ({project_version}) and {PACKAGE_INIT.name} ({package_version})"
        )
    return project_version


def _parse_debian_control_template() -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in DEBIAN_CONTROL_TEMPLATE.read_text(encoding="utf-8").splitlines():
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    if "Package" not in fields:
        raise ValueError(f"could not find Package stanza in {DEBIAN_CONTROL_TEMPLATE}")
    return fields


def render_debian_control(*, version: str, arch: str) -> str:
    template_fields = _parse_debian_control_template()
    rendered = [
        f"Package: {template_fields['Package']}",
        f"Version: {version}",
        f"Section: {template_fields['Section']}",
        f"Priority: {template_fields['Priority']}",
        f"Architecture: {arch}",
        f"Maintainer: {template_fields['Maintainer']}",
        "Depends: python3 (>= 3.11)",
        f"Description: {template_fields['Description']}",
    ]
    return "\n".join(rendered) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("version")
    render_control = subparsers.add_parser("debian-control")
    render_control.add_argument("--arch", required=True)

    args = parser.parse_args(argv)
    if args.command == "version":
        print(require_synced_versions())
        return 0
    if args.command == "debian-control":
        print(render_debian_control(version=require_synced_versions(), arch=args.arch), end="")
        return 0
    print(f"unknown command: {args.command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
