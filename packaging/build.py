from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = PROJECT_ROOT / "packaging" / "dist"
WINDOWS_SPEC = PROJECT_ROOT / "packaging" / "pyinstaller.spec"
INNO_SCRIPT = PROJECT_ROOT / "packaging" / "windows" / "eodinga.iss"


def _audit_windows_inputs() -> dict[str, Any]:
    spec_namespace: dict[str, Any] = {"__file__": str(WINDOWS_SPEC)}
    exec(WINDOWS_SPEC.read_text(encoding="utf-8"), spec_namespace)
    inno_text = INNO_SCRIPT.read_text(encoding="utf-8")
    return {
        "target": "windows-dry-run",
        "pyinstaller_spec": {
            "path": str(WINDOWS_SPEC),
            "exists": WINDOWS_SPEC.exists(),
            "hiddenimports": spec_namespace.get("HIDDEN_IMPORTS", []),
        },
        "inno_setup": {
            "path": str(INNO_SCRIPT),
            "exists": INNO_SCRIPT.exists(),
            "contains_app_version_template": "AppVersion={#AppVersion}" in inno_text,
            "contains_output_name": "OutputBaseFilename=eodinga-setup" in inno_text,
        },
    }


def _write_audit(payload: dict[str, Any]) -> Path:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    target = DIST_DIR / f"{payload['target']}-audit.json"
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target


def _run_windows_dry_run() -> int:
    payload = _audit_windows_inputs()
    _write_audit(payload)
    return 0


def _run_windows() -> int:
    payload = _audit_windows_inputs()
    payload["platform_tools"] = ["pyinstaller", "iscc"]
    _write_audit(payload)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=("windows-dry-run", "windows"), required=True)
    args = parser.parse_args(argv)
    if args.target == "windows-dry-run":
        return _run_windows_dry_run()
    return _run_windows()


if __name__ == "__main__":
    raise SystemExit(main())
