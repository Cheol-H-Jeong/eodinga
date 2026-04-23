from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_linux_appimage_dry_run_archive_is_reproducible() -> None:
    result = subprocess.run(
        [sys.executable, "packaging/build.py", "--target", "linux-appimage-dry-run"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    archive_path = Path("packaging/dist/linux-appimage-audit.json")
    first_archive = Path(json.loads(archive_path.read_text(encoding="utf-8"))["archive"])
    first_hash = _sha256(first_archive)

    result = subprocess.run(
        [sys.executable, "packaging/build.py", "--target", "linux-appimage-dry-run"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    second_archive = Path(json.loads(archive_path.read_text(encoding="utf-8"))["archive"])
    assert _sha256(second_archive) == first_hash


def test_linux_deb_dry_run_archive_is_reproducible() -> None:
    result = subprocess.run(
        [sys.executable, "packaging/build.py", "--target", "linux-deb-dry-run"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    archive_path = Path("packaging/dist/linux-deb-audit.json")
    first_archive = Path(json.loads(archive_path.read_text(encoding="utf-8"))["archive"])
    first_hash = _sha256(first_archive)

    result = subprocess.run(
        [sys.executable, "packaging/build.py", "--target", "linux-deb-dry-run"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    second_archive = Path(json.loads(archive_path.read_text(encoding="utf-8"))["archive"])
    assert _sha256(second_archive) == first_hash
