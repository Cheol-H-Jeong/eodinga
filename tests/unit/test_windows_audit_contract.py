from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_windows_dry_run_preserves_license_and_desktop_shortcut_contract() -> None:
    result = subprocess.run(
        [sys.executable, "packaging/build.py", "--target", "windows-dry-run"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    payload = json.loads(Path("packaging/dist/windows-dry-run-audit.json").read_text(encoding="utf-8"))
    assert payload["inno_setup"]["license_file_exists"] is True
    assert payload["inno_setup"]["contains_rendered_desktop_shortcut"] is True
    assert payload["inno_setup"]["contains_user_desktop_shortcut"] is True
    assert payload["inno_setup"]["purge_targets_local_and_roaming_user_state"] is True
