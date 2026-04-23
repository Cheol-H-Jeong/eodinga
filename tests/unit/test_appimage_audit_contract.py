from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


def test_linux_appimage_dry_run_preserves_source_assets() -> None:
    result = subprocess.run(
        ["bash", "packaging/linux/appimage.sh", "--dry-run"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    payload = json.loads(open("packaging/dist/linux-appimage-audit.json", encoding="utf-8").read())
    assert payload["desktop_entry"]["matches_source_asset"] is True
    assert payload["desktop_entry"]["exec"] == "eodinga gui"
    assert payload["desktop_entry"]["startup_notify"] == "true"
    assert payload["icon"]["matches_source_asset"] is True
    assert payload["runtime_bundle"]["package_exists"] is True
    assert payload["runtime_bundle"]["package_init_exists"] is True
    assert payload["runtime_bundle"]["module_entry_exists"] is True
    assert payload["apprun"]["has_strict_shell"] is True
    assert payload["launcher"]["uses_bundled_runtime"] is True
    assert payload["appimage_path"].endswith(f"-linux-{payload['arch']}.AppImage")
    assert payload["appimage_artifact"]["path"] == payload["appimage_path"]
    assert payload["appimage_artifact"]["exists"] is False
    assert payload["appimage_artifact"]["build_tool"] == "appimagetool"
    assert {
        ".DirIcon",
        "AppRun",
        "usr/bin/eodinga",
        "usr/share/applications/eodinga.desktop",
        "usr/share/icons/hicolor/scalable/apps/eodinga.svg",
    } <= set(payload["appdir_manifest"])


def test_linux_appimage_build_writes_appimage_artifact(tmp_path: Path) -> None:
    tool_path = tmp_path / "appimagetool"
    tool_path.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "printf 'fake appimage for %s\\n' \"$1\" > \"$2\"\n"
        "chmod +x \"$2\"\n",
        encoding="utf-8",
    )
    tool_path.chmod(0o755)

    env = os.environ.copy()
    env["APPIMAGE_TOOL"] = str(tool_path)
    result = subprocess.run(
        ["bash", "packaging/linux/appimage.sh"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    payload = json.loads(Path("packaging/dist/linux-appimage-audit.json").read_text(encoding="utf-8"))
    appimage_artifact = payload["appimage_artifact"]
    assert payload["target"] == "linux-appimage"
    assert payload["dry_run"] is False
    assert Path(payload["appimage_path"]).name == f"eodinga-{payload['version']}-linux-{payload['arch']}.AppImage"
    assert appimage_artifact["path"] == payload["appimage_path"]
    assert appimage_artifact["exists"] is True
    assert appimage_artifact["size_bytes"] > 0
    assert len(appimage_artifact["sha256"]) == 64
    assert appimage_artifact["is_executable"] is True
    assert appimage_artifact["build_tool"] == str(tool_path)
