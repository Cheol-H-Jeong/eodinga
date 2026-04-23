from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_linux_deb_dry_run_preserves_assets_and_reproducible_changelog() -> None:
    result = subprocess.run(
        ["bash", "packaging/linux/deb.sh", "--dry-run"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    payload = json.loads(Path("packaging/dist/linux-deb-audit.json").read_text(encoding="utf-8"))
    assert payload["debian_changelog_template"]["contains_version_template"] is True
    assert payload["debian_changelog_template"]["rendered_exists"] is True
    assert payload["debian_changelog_template"]["rendered_version_matches_package"] is True
    assert payload["desktop_entry"]["matches_source_asset"] is True
    assert payload["desktop_entry"]["startup_notify"] == "true"
    assert payload["icon"]["matches_source_asset"] is True
    assert payload["source_tree"]["exists"] is True
    assert payload["source_tree"]["package_init_exists"] is True
    assert payload["launcher"]["has_strict_shell"] is True
    assert payload["launcher"]["uses_packaged_lib_path"] is True
    assert payload["docs"]["changelog_gzip_mtime_zero"] is True
