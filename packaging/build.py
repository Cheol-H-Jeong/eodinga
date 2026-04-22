from __future__ import annotations

import argparse
import json
import re
import subprocess
import tomllib
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = PROJECT_ROOT / "packaging" / "dist"
WINDOWS_SPEC = PROJECT_ROOT / "packaging" / "pyinstaller.spec"
INNO_SCRIPT = PROJECT_ROOT / "packaging" / "windows" / "eodinga.iss"
PACKAGE_INIT = PROJECT_ROOT / "eodinga" / "__init__.py"
PYPROJECT = PROJECT_ROOT / "pyproject.toml"
APPIMAGE_SCRIPT = PROJECT_ROOT / "packaging" / "linux" / "appimage.sh"
APPIMAGE_DESKTOP = PROJECT_ROOT / "packaging" / "linux" / "eodinga.desktop"
INNO_VERSION_TOKEN = "@@APP_VERSION@@"


def _read_project_version() -> str:
    payload = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    return str(payload["project"]["version"])


def _read_package_version() -> str:
    match = re.search(
        r'^__version__\s*=\s*"(?P<version>[^"]+)"',
        PACKAGE_INIT.read_text(encoding="utf-8"),
        flags=re.MULTILINE,
    )
    if match is None:
        raise ValueError(f"could not determine package version from {PACKAGE_INIT}")
    return match.group("version")


def _render_inno_script(version: str) -> Path:
    rendered = INNO_SCRIPT.read_text(encoding="utf-8").replace(INNO_VERSION_TOKEN, version)
    rendered_path = DIST_DIR / "windows" / "eodinga.iss"
    rendered_path.parent.mkdir(parents=True, exist_ok=True)
    rendered_path.write_text(rendered, encoding="utf-8")
    return rendered_path


def _audit_windows_inputs(version: str, package_version: str) -> dict[str, Any]:
    spec_namespace: dict[str, Any] = {"__file__": str(WINDOWS_SPEC)}
    exec(WINDOWS_SPEC.read_text(encoding="utf-8"), spec_namespace)
    inno_text = INNO_SCRIPT.read_text(encoding="utf-8")
    rendered_path = _render_inno_script(version)
    return {
        "target": "windows-dry-run",
        "version": version,
        "package_version": package_version,
        "version_matches_package": version == package_version,
        "pyinstaller_spec": {
            "path": str(WINDOWS_SPEC),
            "exists": WINDOWS_SPEC.exists(),
            "hiddenimports": spec_namespace.get("HIDDEN_IMPORTS", []),
        },
        "inno_setup": {
            "path": str(INNO_SCRIPT),
            "exists": INNO_SCRIPT.exists(),
            "contains_app_version_template": INNO_VERSION_TOKEN in inno_text,
            "rendered_path": str(rendered_path),
            "contains_output_name": "OutputBaseFilename=eodinga-setup" in inno_text,
        },
    }


def _write_audit(payload: dict[str, Any]) -> Path:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    target = DIST_DIR / f"{payload['target']}-audit.json"
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target


def _run_windows_dry_run() -> int:
    version = _read_project_version()
    package_version = _read_package_version()
    payload = _audit_windows_inputs(version, package_version)
    _write_audit(payload)
    return 0


def _run_windows() -> int:
    version = _read_project_version()
    package_version = _read_package_version()
    payload = _audit_windows_inputs(version, package_version)
    payload["platform_tools"] = ["pyinstaller", "iscc"]
    _write_audit(payload)
    return 0


def _run_linux_appimage_dry_run() -> int:
    result = subprocess.run(
        ["bash", str(APPIMAGE_SCRIPT), "--dry-run"],
        cwd=PROJECT_ROOT,
        check=False,
    )
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--target",
        choices=("linux-appimage-dry-run", "windows-dry-run", "windows"),
        required=True,
    )
    args = parser.parse_args(argv)
    if args.target == "linux-appimage-dry-run":
        return _run_linux_appimage_dry_run()
    if args.target == "windows-dry-run":
        return _run_windows_dry_run()
    return _run_windows()


if __name__ == "__main__":
    raise SystemExit(main())
