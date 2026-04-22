from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from eodinga import __version__


def test_build_dry_run_returns_zero_and_writes_audit() -> None:
    result = subprocess.run(
        [sys.executable, "packaging/build.py", "--target", "windows-dry-run"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    audit_path = Path("packaging/dist/windows-dry-run-audit.json")
    assert audit_path.exists()
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    assert payload["target"] == "windows-dry-run"
    assert payload["version"] == __version__
    assert payload["version_matches_package"] is True
    assert payload["pyinstaller_spec"]["exists"] is True
    rendered_path = Path(payload["inno_setup"]["rendered_path"])
    assert rendered_path.exists()
    rendered_text = rendered_path.read_text(encoding="utf-8")
    assert f'#define AppVersion "{__version__}"' in rendered_text
    assert "@@APP_VERSION@@" not in rendered_text


def test_linux_appimage_dry_run_stages_recipe() -> None:
    result = subprocess.run(
        ["bash", "packaging/linux/appimage.sh", "--dry-run"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    manifest_path = Path("packaging/dist/linux-appimage-audit.json")
    assert manifest_path.exists()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["target"] == "linux-appimage-dry-run"
    assert payload["version"] == __version__
    assert Path(payload["appdir"]).exists()
    assert Path(payload["archive"]).exists()
