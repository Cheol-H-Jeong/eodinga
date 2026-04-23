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
    assert payload["icon"]["matches_source_asset"] is True
    assert payload["runtime_bundle"]["package_exists"] is True
    assert payload["runtime_bundle"]["package_init_exists"] is True
    assert payload["runtime_bundle"]["module_entry_exists"] is True
    assert payload["runtime_bundle"]["i18n_ko_exists"] is True
    assert payload["runtime_bundle"]["package_data_paths_match_declared"] is True
    assert payload["apprun"]["has_strict_shell"] is True
    assert payload["launcher"]["uses_bundled_runtime"] is True
