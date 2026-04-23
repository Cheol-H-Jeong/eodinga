from __future__ import annotations

import json
import subprocess


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
    assert payload["archive_sha256_file_exists"] is True
    assert payload["archive_sha256_matches_file"] is True
    assert payload["icon"]["matches_source_asset"] is True
    assert payload["apprun"]["has_strict_shell"] is True
    assert payload["launcher"]["changes_to_project_root"] is True
