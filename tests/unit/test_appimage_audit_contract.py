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
    assert payload["recipe"]["app_id"] == "io.github.cheolhjeong.eodinga"
    assert payload["recipe"]["app_exec"] == "usr/bin/eodinga"
    assert payload["recipe"]["app_exec_args"] == "gui"
    assert payload["recipe"]["rendered_version_token_removed"] is True
    assert payload["recipe"]["includes_desktop_entry"] is True
    assert payload["recipe"]["includes_icon_asset"] is True
    assert payload["icon"]["matches_source_asset"] is True
    assert payload["apprun"]["has_strict_shell"] is True
    assert payload["launcher"]["changes_to_project_root"] is True
