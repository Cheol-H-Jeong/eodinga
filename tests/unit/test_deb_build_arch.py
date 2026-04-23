from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from eodinga import __version__


def test_linux_deb_dry_run_normalizes_x86_64_target_arch() -> None:
    env = os.environ.copy()
    env["TARGET_ARCH"] = "x86_64"

    result = subprocess.run(
        [sys.executable, "packaging/build.py", "--target", "linux-deb-dry-run"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(Path("packaging/dist/linux-deb-audit.json").read_text(encoding="utf-8"))
    assert payload["requested_arch"] == "x86_64"
    assert payload["arch"] == "amd64"
    assert Path(payload["archive"]).name == f"eodinga_{__version__}_amd64_debroot.tar.gz"
    assert Path(payload["deb_path"]).name == f"eodinga_{__version__}_amd64.deb"
    assert payload["control"]["architecture"] == "amd64"


def test_linux_deb_dry_run_normalizes_aarch64_target_arch() -> None:
    env = os.environ.copy()
    env["TARGET_ARCH"] = "aarch64"

    result = subprocess.run(
        ["bash", "packaging/linux/deb.sh", "--dry-run"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(Path("packaging/dist/linux-deb-audit.json").read_text(encoding="utf-8"))
    assert payload["requested_arch"] == "aarch64"
    assert payload["arch"] == "arm64"
    assert Path(payload["archive"]).name == f"eodinga_{__version__}_arm64_debroot.tar.gz"
    assert Path(payload["deb_path"]).name == f"eodinga_{__version__}_arm64.deb"
    assert payload["control"]["architecture"] == "arm64"
